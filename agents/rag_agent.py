"""
RAG Agent for literature review question answering using DSPy
"""
import dspy
import os
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import numpy as np
from pathlib import Path
import json

# Load environment variables from the project's .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
OPENAI_KEY = os.getenv("OPENAI_KEY")
class RAGSignature(dspy.Signature):
    """Answer questions about literature review papers using retrieved context."""
    
    question: str = dspy.InputField(desc="The user's question about the literature")
    context: str = dspy.InputField(desc="Relevant context from retrieved papers")
    
    answer: str = dspy.OutputField(desc="A comprehensive answer based on the context")


class RAGAgent(dspy.Module):
    """RAG Agent that retrieves relevant papers and answers questions using DSPy."""
    
    def __init__(self, vector_db_path: str = "data/rag_embeddings", api_key: str = None):
        super().__init__()
        self.vector_db_path = Path(vector_db_path)
        self.vector_db_path.mkdir(parents=True, exist_ok=True)
        
        # Store the API key for use in operations
        self.api_key = api_key if api_key else OPENAI_KEY
        
        # Configure DSPy with the API key if available
        if self.api_key and self.api_key != "your_openai_api_key_here":
            # Set the environment variable for DSPy
            os.environ["OPENAI_API_KEY"] = self.api_key
            
            # Import the safe configuration from orchestrator
            try:
                from .orchestrator import configure_dspy_safely
                configure_dspy_safely(self.api_key)
            except ImportError:
                # Fallback if orchestrator not available
                lm = dspy.LM(api_key=self.api_key, model="gpt-4o-mini", max_tokens=256)
                dspy.configure(lm=lm)
        
        # Initialize DSPy embedder (using default dimensions for consistency)
        self.embedder = dspy.Embedder('openai/text-embedding-3-small')
        
        # Initialize DSPy predictor
        self.predictor = dspy.Predict(RAGSignature)
        
        # Load or create vector database
        self._load_vector_db()
        
        # Don't load papers during initialization - load them when needed for specific projects
    
    def _load_vector_db(self):
        """Load the vector database from disk."""
        self.embeddings_file = self.vector_db_path / "embeddings.npy"
        self.metadata_file = self.vector_db_path / "metadata.json"
        
        if self.embeddings_file.exists() and self.metadata_file.exists():
            self.embeddings = np.load(self.embeddings_file)
            with open(self.metadata_file, 'r') as f:
                self.metadata = json.load(f)
        else:
            self.embeddings = np.array([])
            self.metadata = []
    
    def _save_vector_db(self):
        """Save the vector database to disk."""
        np.save(self.embeddings_file, self.embeddings)
        with open(self.metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2)
    
    def _get_embedding(self, text: str) -> np.ndarray:
        """Get embedding for text using DSPy embedder."""
        return self.embedder(text)
    
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
                
                # Convert to RAG format
                papers_for_rag = []
                for paper in project_papers:
                    papers_for_rag.append({
                        'id': paper['id'],
                        'title': paper['title'],
                        'abstract': paper['abstract'],
                        'authors': paper['authors'],
                        'year': paper['year'],
                        'venue': paper['venue'],
                        'doi': paper['doi'],
                        'status': paper['status'],
                        'score': paper['score'],
                        'rationale': paper['rationale'],
                        'project_id': paper['project_id']
                    })
                
                # Add papers to RAG agent (this will generate embeddings)
                # Use the actual project_id from the database, not 0
                for paper in papers_for_rag:
                    self.add_papers([paper], project_id=paper['project_id'])
                print(f"DEBUG: Loaded {len(papers_for_rag)} papers into RAG agent")
                
        except Exception as e:
            print(f"DEBUG: Warning - Failed to load papers from database: {e}")
            import traceback
            traceback.print_exc()
    
    def add_papers(self, papers: List[Dict[str, Any]], project_id: int):
        """Add papers to the vector database with embeddings."""
        # Check for existing papers to avoid duplicates
        existing_paper_ids = {meta.get('paper_id') for meta in self.metadata}
        
        # Prepare texts for embedding
        texts = []
        paper_metadata = []
        
        for paper in papers:
            paper_id = paper.get('id')
            if paper_id in existing_paper_ids:
                # Update project_id in existing metadata if different
                for i, meta in enumerate(self.metadata):
                    if meta.get('paper_id') == paper_id:
                        old_project_id = meta.get('project_id')
                        if old_project_id != project_id:
                            print(f"DEBUG: Updating project_id for paper {paper_id} from {old_project_id} to {project_id}")
                            self.metadata[i]['project_id'] = project_id
                            self._save_vector_db()
                        else:
                            print(f"DEBUG: Skipping duplicate paper ID {paper_id} (already in project {project_id})")
                        break
                continue
                
            # Combine title and abstract for embedding
            text = f"Title: {paper.get('title', '')}\nAbstract: {paper.get('abstract', '')}"
            texts.append(text)
            paper_metadata.append({
                'paper_id': paper_id,
                'project_id': project_id,
                'title': paper.get('title', ''),
                'abstract': paper.get('abstract', ''),
                'authors': paper.get('authors', ''),
                'year': paper.get('year'),
                'venue': paper.get('venue', ''),
                'doi': paper.get('doi', ''),
                'status': paper.get('status', ''),
                'score': paper.get('score'),
                'rationale': paper.get('rationale', '')
            })
        
        # Get embeddings using DSPy embedder
        if texts:
            new_embeddings = self.embedder(texts)
            
            # Add to existing database
            if len(self.embeddings) == 0:
                self.embeddings = new_embeddings
                self.metadata = paper_metadata
            else:
                self.embeddings = np.vstack([self.embeddings, new_embeddings])
                self.metadata.extend(paper_metadata)
            
            # Save to disk
            self._save_vector_db()
    
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
        
        # Get embeddings using DSPy embedder
        if texts:
            new_embeddings = self.embedder(texts)
            
            # Add to existing database
            if len(self.embeddings) == 0:
                self.embeddings = new_embeddings
                self.metadata = summary_metadata
            else:
                self.embeddings = np.vstack([self.embeddings, new_embeddings])
                self.metadata.extend(summary_metadata)
            
            # Save to disk
            self._save_vector_db()
    
    def retrieve_relevant_papers(self, question: str, project_id: int, top_k: int = 5) -> List[Dict[str, Any]]:
        """Retrieve most relevant papers for a question."""
        if len(self.embeddings) == 0:
            print("DEBUG: No embeddings available for retrieval")
            return []
        
        print(f"DEBUG: Retrieving papers for project {project_id}, question: '{question}'")
        
        # Get embedding for the question
        question_embedding = self._get_embedding(question)
        
        # Calculate similarities
        similarities = []
        for i, embedding in enumerate(self.embeddings):
            # Only consider papers from the same project (or all papers if project_id is 0)
            paper_project_id = self.metadata[i].get('project_id')
            # Convert to int for comparison (handle None and string cases)
            try:
                paper_project_id = int(paper_project_id) if paper_project_id is not None else None
                project_id_int = int(project_id) if project_id is not None else None
            except (ValueError, TypeError):
                paper_project_id = None
                project_id_int = None
            
            if project_id_int == 0 or paper_project_id == project_id_int:
                similarity = self._cosine_similarity(question_embedding, embedding)
                similarities.append((i, similarity))
        
        print(f"DEBUG: Found {len(similarities)} papers matching project criteria (project_id={project_id}, total embeddings={len(self.embeddings)})")
        if len(similarities) == 0 and len(self.embeddings) > 0:
            # Debug: show project_ids in metadata
            project_ids_in_metadata = [m.get('project_id') for m in self.metadata]
            print(f"DEBUG: Project IDs in metadata: {set(project_ids_in_metadata)}")
        
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
        
        # Generate answer using DSPy
        result = self.predictor(question=question, context=context)
        
        # Format the answer with relevant papers
        answer = result.answer
        
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
