"""
RAG Agent for literature review question answering using Azure OpenAI
"""
import os
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import numpy as np
from pathlib import Path
import json
from agents.azure_config import chat_completion, get_embedding, get_embeddings_batch

load_dotenv()


class RAGAgent:
    """RAG Agent that retrieves relevant papers and answers questions using Azure OpenAI.
    
    Supports project-specific vector databases for better isolation.
    When project_id is provided, uses project-specific vector database.
    Otherwise, uses shared vector database for backward compatibility.
    """

    def __init__(self, vector_db_path: str = "data/rag_embeddings", api_key: str = None, project_id: Optional[int] = None):
        """
        Initialize RAG Agent.
        
        Args:
            vector_db_path: Base path for vector database storage
            api_key: Not used (kept for backward compatibility, Azure uses env config)
            project_id: Optional project ID for project-specific vector database
        """
        base_path = Path(vector_db_path)
        
        # Use project-specific path if project_id is provided
        if project_id is not None:
            self.vector_db_path = base_path / f"project_{project_id}"
        else:
            self.vector_db_path = base_path / "shared"
        
        self.vector_db_path.mkdir(parents=True, exist_ok=True)
        self.project_id = project_id

        # Load or create vector database
        self._load_vector_db()
    
    def _load_vector_db(self):
        """Load the vector database from disk."""
        self.embeddings_file = self.vector_db_path / "embeddings.npy"
        self.metadata_file = self.vector_db_path / "metadata.json"
        
        try:
            if self.embeddings_file.exists() and self.metadata_file.exists():
                self.embeddings = np.load(self.embeddings_file)
                with open(self.metadata_file, 'r') as f:
                    self.metadata = json.load(f)
                print(f"DEBUG: Loaded vector database from {self.vector_db_path} ({len(self.metadata)} items)")
            else:
                self.embeddings = np.array([])
                self.metadata = []
                print(f"DEBUG: Created new vector database at {self.vector_db_path}")
        except Exception as e:
            print(f"DEBUG: Error loading vector database: {e}")
            self.embeddings = np.array([])
            self.metadata = []
    
    def _save_vector_db(self):
        """Save the vector database to disk."""
        try:
            np.save(self.embeddings_file, self.embeddings)
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            print(f"DEBUG: Error saving vector database: {e}")
            raise
    
    def _get_embedding(self, text: str) -> np.ndarray:
        """Get embedding for text using Azure OpenAI.
        
        Args:
            text: Text to embed
            
        Returns:
            Numpy array of embedding vector
            
        Raises:
            Exception: If embedding generation fails
        """
        try:
            return np.array(get_embedding(text))
        except Exception as e:
            print(f"DEBUG: Error getting embedding: {e}")
            raise
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    
    def _load_papers_from_db(self, project_id: int = None):
        """Load papers from SQLite database and generate embeddings if not already present."""
        try:
            from db.connection import connect
            from db.repository import list_included, list_maybe
            
            print("DEBUG: Loading papers from SQLite database...")
            
            with connect() as con:
                if project_id is not None:
                    # Load papers from specific project only
                    included_papers = list_included(con, project_id)
                    maybe_papers = list_maybe(con, project_id)
                    project_papers = included_papers + maybe_papers
                    print(f"DEBUG: Project {project_id} has {len(project_papers)} papers")
                else:
                    # Load papers from all projects (for backward compatibility)
                    projects = con.execute("SELECT id FROM projects").fetchall()
                    print(f"DEBUG: Found {len(projects)} projects in database")
                    
                    all_papers = []
                    for proj_id, in projects:
                        included_papers = list_included(con, proj_id)
                        maybe_papers = list_maybe(con, proj_id)
                        project_papers = included_papers + maybe_papers
                        
                        print(f"DEBUG: Project {proj_id} has {len(project_papers)} papers")
                        all_papers.extend(project_papers)
                    
                    project_papers = all_papers
                
                if not project_papers:
                    print("DEBUG: No papers found in database")
                    return
                
                # Convert to RAG format and group by project_id for batch processing
                papers_by_project = {}
                for paper in project_papers:
                    paper_project_id = paper.get('project_id')
                    if paper_project_id not in papers_by_project:
                        papers_by_project[paper_project_id] = []
                    
                    papers_by_project[paper_project_id].append({
                        'id': paper['id'],
                        'title': paper.get('title', ''),
                        'abstract': paper.get('abstract', ''),
                        'authors': paper.get('authors', ''),
                        'year': paper.get('year'),
                        'venue': paper.get('venue', ''),
                        'doi': paper.get('doi', ''),
                        'status': paper.get('status', ''),
                        'score': paper.get('score'),
                        'rationale': paper.get('rationale', ''),
                        'project_id': paper_project_id
                    })
                
                # Batch add papers by project (efficient embedding generation)
                total_loaded = 0
                for paper_project_id, papers_batch in papers_by_project.items():
                    if papers_batch:
                        self.add_papers(papers_batch, project_id=paper_project_id)
                        total_loaded += len(papers_batch)
                        print(f"DEBUG: Loaded {len(papers_batch)} papers for project {paper_project_id}")
                
                print(f"DEBUG: Total loaded {total_loaded} papers into RAG agent")
                
        except Exception as e:
            print(f"DEBUG: Warning - Failed to load papers from database: {e}")
            import traceback
            traceback.print_exc()
    
    def add_papers(self, papers: List[Dict[str, Any]], project_id: int):
        """Add papers to the vector database with embeddings.
        
        Args:
            papers: List of paper dicts with 'id' key (paper ID from database)
            project_id: Project ID to associate papers with
        """
        if not papers:
            return
        
        # Check for existing papers to avoid duplicates
        # Metadata uses 'paper_id' key which corresponds to paper 'id' from database
        existing_paper_ids = {meta.get('paper_id') for meta in self.metadata if meta.get('type') != 'agent_summary'}
        
        # Prepare texts for embedding
        texts = []
        paper_metadata = []
        skipped_count = 0
        
        for paper in papers:
            paper_id = paper.get('id')  # Paper ID from database
            if paper_id is None:
                print(f"DEBUG: Skipping paper with no ID")
                skipped_count += 1
                continue
                
            if paper_id in existing_paper_ids:
                # Update project_id in existing metadata if different
                for i, meta in enumerate(self.metadata):
                    if meta.get('paper_id') == paper_id and meta.get('type') != 'agent_summary':
                        old_project_id = meta.get('project_id')
                        if old_project_id != project_id:
                            print(f"DEBUG: Updating project_id for paper {paper_id} from {old_project_id} to {project_id}")
                            self.metadata[i]['project_id'] = project_id
                            self._save_vector_db()
                        else:
                            print(f"DEBUG: Skipping duplicate paper ID {paper_id} (already in project {project_id})")
                        break
                skipped_count += 1
                continue
                
            # Combine title and abstract for embedding
            text = f"Title: {paper.get('title', '')}\nAbstract: {paper.get('abstract', '')}"
            texts.append(text)
            paper_metadata.append({
                'paper_id': paper_id,  # Store as paper_id in metadata for consistency
                'project_id': project_id,
                'title': paper.get('title', ''),
                'abstract': paper.get('abstract', ''),
                'authors': paper.get('authors', ''),
                'year': paper.get('year'),
                'venue': paper.get('venue', ''),
                'doi': paper.get('doi', ''),
                'status': paper.get('status', ''),
                'score': paper.get('score'),
                'rationale': paper.get('rationale', ''),
                'type': 'paper'  # Mark as paper vs summary
            })

        # Get embeddings using Azure OpenAI (batch processing)
        if texts:
            try:
                print(f"DEBUG: Generating embeddings for {len(texts)} papers (skipped {skipped_count} duplicates)")
                embeddings_list = get_embeddings_batch(texts)
                new_embeddings = np.array(embeddings_list)

                # Add to existing database
                if len(self.embeddings) == 0:
                    self.embeddings = new_embeddings
                    self.metadata = paper_metadata
                else:
                    self.embeddings = np.vstack([self.embeddings, new_embeddings])
                    self.metadata.extend(paper_metadata)
                
                # Save to disk
                self._save_vector_db()
                print(f"DEBUG: Successfully added {len(paper_metadata)} papers to vector database")
            except Exception as e:
                print(f"DEBUG: Error generating embeddings: {e}")
                import traceback
                traceback.print_exc()
                raise
        elif skipped_count > 0:
            print(f"DEBUG: All {skipped_count} papers were duplicates, nothing to add")
    
    def _load_agent_summaries_from_db(self, project_id: int = None):
        """Load agent summaries from SQLite database and generate embeddings if not already present."""
        try:
            from db.connection import connect
            from db.repository import get_agent_summaries
            
            print(f"DEBUG: Loading agent summaries from SQLite database for project {project_id}...")
            
            with connect() as con:
                if project_id is not None:
                    summaries = get_agent_summaries(con, project_id)
                    print(f"DEBUG: Project {project_id} has {len(summaries)} agent summaries")
                else:
                    print("DEBUG: Loading summaries for all projects not implemented yet")
                    summaries = []
                
                if not summaries:
                    print("DEBUG: No agent summaries found")
                    return
                
                # Convert summaries to RAG format
                summaries_for_rag = []
                for summary in summaries:
                    # Combine summary fields for embedding
                    summary_text = (
                        f"Paper: {summary.get('title', '')}\n"
                        f"Population: {summary.get('population', '')}\n"
                        f"Intervention: {summary.get('intervention', '')}\n"
                        f"Comparator: {summary.get('comparator', '')}\n"
                        f"Outcomes: {summary.get('outcomes', '')}\n"
                        f"Main Findings: {summary.get('main_findings', '')}\n"
                        f"Sample Size: {summary.get('sample_size', '')}"
                    )
                    
                    summaries_for_rag.append({
                        'summary_id': summary.get('summary_id'),
                        'paper_id': summary.get('paper_id'),
                        'project_id': summary.get('project_id'),
                        'title': summary.get('title', ''),
                        'text': summary_text,
                        'population': summary.get('population', ''),
                        'intervention': summary.get('intervention', ''),
                        'comparator': summary.get('comparator', ''),
                        'outcomes': summary.get('outcomes', ''),
                        'main_findings': summary.get('main_findings', ''),
                        'sample_size': summary.get('sample_size', ''),
                        'type': 'agent_summary'  # Mark as summary vs paper
                    })
                
                # Add summaries to RAG agent
                self.add_summaries(summaries_for_rag, project_id)
                print(f"DEBUG: Loaded {len(summaries_for_rag)} summaries into RAG agent")
                
        except Exception as e:
            print(f"DEBUG: Warning - Failed to load agent summaries from database: {e}")
            import traceback
            traceback.print_exc()
    
    def add_summaries(self, summaries: List[Dict[str, Any]], project_id: int):
        """Add agent summaries to the vector database with embeddings."""
        # Check for existing summaries to avoid duplicates
        existing_summary_ids = {
            meta.get('summary_id') for meta in self.metadata 
            if meta.get('type') == 'agent_summary'
        }
        
        # Prepare texts for embedding
        texts = []
        summary_metadata = []
        
        for summary in summaries:
            summary_id = summary.get('summary_id')
            if summary_id in existing_summary_ids:
                continue
            
            # Use the summary text for embedding
            text = summary.get('text', '')
            texts.append(text)
            
            summary_metadata.append({
                'summary_id': summary_id,
                'paper_id': summary.get('paper_id'),
                'project_id': project_id,
                'title': summary.get('title', ''),
                'text': text,
                'population': summary.get('population', ''),
                'intervention': summary.get('intervention', ''),
                'comparator': summary.get('comparator', ''),
                'outcomes': summary.get('outcomes', ''),
                'main_findings': summary.get('main_findings', ''),
                'sample_size': summary.get('sample_size', ''),
                'type': 'agent_summary'
            })
        
        # Get embeddings using Azure OpenAI
        if texts:
            try:
                print(f"DEBUG: Generating embeddings for {len(texts)} summaries")
                embeddings_list = get_embeddings_batch(texts)
                new_embeddings = np.array(embeddings_list)

                # Add to existing database
                if len(self.embeddings) == 0:
                    self.embeddings = new_embeddings
                    self.metadata = summary_metadata
                else:
                    self.embeddings = np.vstack([self.embeddings, new_embeddings])
                    self.metadata.extend(summary_metadata)

                # Save to disk
                self._save_vector_db()
                print(f"DEBUG: Successfully added {len(summary_metadata)} summaries to vector database")
            except Exception as e:
                print(f"DEBUG: Error generating summary embeddings: {e}")
                import traceback
                traceback.print_exc()
                raise
    
    def retrieve_relevant_papers(self, question: str, project_id: int, top_k: int = 5) -> List[Dict[str, Any]]:
        """Retrieve most relevant papers for a question.
        
        Args:
            question: The question to retrieve papers for
            project_id: Project ID to filter papers (must match)
            top_k: Number of top papers to retrieve
            
        Returns:
            List of relevant paper/summary metadata dictionaries
        """
        if len(self.embeddings) == 0:
            print("DEBUG: No embeddings available for retrieval")
            return []
        
        print(f"DEBUG: Retrieving papers for project {project_id}, question: '{question}'")
        
        # Get embedding for the question
        try:
            question_embedding = self._get_embedding(question)
        except Exception as e:
            print(f"DEBUG: Error getting question embedding: {e}")
            return []
        
        # Calculate similarities with project filtering
        similarities = []
        project_id_int = int(project_id) if project_id is not None else None
        
        for i, embedding in enumerate(self.embeddings):
            # Get paper project ID from metadata
            paper_project_id = self.metadata[i].get('project_id')
            
            # Convert to int for comparison (handle None and string cases)
            try:
                paper_project_id = int(paper_project_id) if paper_project_id is not None else None
            except (ValueError, TypeError):
                paper_project_id = None
            
            # Filter by project_id (strict matching)
            # If using project-specific vector DB, all items should match, but double-check
            if paper_project_id == project_id_int or (self.project_id is None and project_id_int == paper_project_id):
                try:
                    similarity = self._cosine_similarity(question_embedding, embedding)
                    similarities.append((i, similarity))
                except Exception as e:
                    print(f"DEBUG: Error calculating similarity for item {i}: {e}")
                    continue
        
        print(f"DEBUG: Found {len(similarities)} papers matching project {project_id} (total embeddings={len(self.embeddings)})")
        if len(similarities) == 0 and len(self.embeddings) > 0:
            # Debug: show project_ids in metadata
            project_ids_in_metadata = [m.get('project_id') for m in self.metadata]
            unique_project_ids = set(p for p in project_ids_in_metadata if p is not None)
            print(f"DEBUG: Project IDs in metadata: {unique_project_ids} (looking for {project_id_int})")
        
        # Sort by similarity and get top_k
        similarities.sort(key=lambda x: x[1], reverse=True)
        top_indices = [idx for idx, _ in similarities[:top_k]]
        
        retrieved_papers = [self.metadata[idx] for idx in top_indices]
        print(f"DEBUG: Retrieved {len(retrieved_papers)} most relevant papers")
        
        return retrieved_papers
    
    def forward(self, question: str, project_id: int, top_k: int = 5) -> str:
        """Answer a question using RAG."""
        # Retrieve relevant papers
        relevant_papers = self.retrieve_relevant_papers(question, project_id, top_k)
        
        if not relevant_papers:
            return "I don't have any relevant papers in the database for this project. Please run a literature review first to populate the database."
        
        # Format context from retrieved papers and summaries
        context_parts = []
        for i, item in enumerate(relevant_papers, 1):
            if item.get('type') == 'agent_summary':
                # This is an agent summary
                context_parts.append(f"Summary {i}:")
                context_parts.append(f"Paper Title: {item.get('title', 'N/A')}")
                if item.get('population'):
                    context_parts.append(f"Population: {item.get('population')}")
                if item.get('intervention'):
                    context_parts.append(f"Intervention: {item.get('intervention')}")
                if item.get('comparator'):
                    context_parts.append(f"Comparator: {item.get('comparator')}")
                if item.get('outcomes'):
                    context_parts.append(f"Outcomes: {item.get('outcomes')}")
                if item.get('main_findings'):
                    context_parts.append(f"Main Findings: {item.get('main_findings')}")
                if item.get('sample_size'):
                    context_parts.append(f"Sample Size: {item.get('sample_size')}")
            else:
                # This is a regular paper
                context_parts.append(f"Paper {i}:")
                context_parts.append(f"Title: {item.get('title', 'N/A')}")
                context_parts.append(f"Authors: {item.get('authors', 'N/A')}")
                context_parts.append(f"Year: {item.get('year', 'N/A')}")
                context_parts.append(f"Venue: {item.get('venue', 'N/A')}")
                context_parts.append(f"Abstract: {item.get('abstract', 'N/A')}")
                if item.get('status'):
                    context_parts.append(f"Status: {item.get('status')}")
                if item.get('score'):
                    context_parts.append(f"Relevance Score: {item.get('score')}")
                if item.get('rationale'):
                    context_parts.append(f"Rationale: {item.get('rationale')}")
            context_parts.append("")  # Empty line between items
        
        context = "\n".join(context_parts)

        # Generate answer using Azure OpenAI
        prompt = f"""Answer the following question using the provided context from literature review papers.

Question: {question}

Context:
{context}

Provide a comprehensive answer based on the context."""

        try:
            messages = [{"role": "user", "content": prompt}]
            answer = chat_completion(messages, agent_type="rag")
        except Exception as e:
            print(f"DEBUG: Error generating RAG answer: {e}")
            import traceback
            traceback.print_exc()
            return f"I encountered an error while generating an answer: {str(e)}. Please try again or contact support."
        
        # Add relevant papers section
        papers_section = "\n\n**Relevant Papers:**\n"
        for i, paper in enumerate(relevant_papers, 1):
            papers_section += f"{i}. **{paper.get('title', 'N/A')}** ({paper.get('year', 'N/A')})\n"
            papers_section += f"   - Authors: {paper.get('authors', 'N/A')}\n"
            papers_section += f"   - Venue: {paper.get('venue', 'N/A')}\n"
            if paper.get('doi'):
                papers_section += f"   - DOI: {paper.get('doi')}\n"
            papers_section += "\n"
        
        return answer + papers_section
    
    def get_paper_summary(self, project_id: int) -> str:
        """Get a summary of all papers in the project."""
        project_papers = [paper for paper in self.metadata if paper.get('project_id') == project_id]
        
        if not project_papers:
            return "No papers found for this project."
        
        summary_parts = [f"Project has {len(project_papers)} papers:"]
        
        for i, paper in enumerate(project_papers, 1):
            summary_parts.append(f"{i}. {paper.get('title', 'N/A')} ({paper.get('year', 'N/A')})")
            summary_parts.append(f"   Authors: {paper.get('authors', 'N/A')}")
            summary_parts.append(f"   Status: {paper.get('status', 'N/A')}")
            if paper.get('score'):
                summary_parts.append(f"   Score: {paper.get('score')}")
            summary_parts.append("")
        
        return "\n".join(summary_parts)
