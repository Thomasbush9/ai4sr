import marimo

__generated_with = "0.13.15"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
    # Searching Papers 

    Todo:

    1. Use multiple sources
    2. add screening
    """
    )
    return


@app.cell
def _():
    import marimo as mo
    import requests
    from urllib.parse import quote
    from bs4 import BeautifulSoup
    return mo, quote, requests


@app.cell
def _(quote, requests):
    keywords = "addiction AND cocaine AND cannabis"
    year_from = 2020
    year_to = 2023
    if year_to:
            url = (
            f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            f"?db=pubmed&term={quote(keywords)}"
            f"&retmax=100&retmode=json"
            f"&mindate={year_from}&maxdate={year_to}&datetype=pdat"
        )

            ids = requests.get(url).json()['esearchresult']['idlist']
    else:
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term{quote(keywords)}&retmax=100&retmode=json"
        ids = requests.get(url).json()['esearchresult']['idlist']
    return ids, keywords


@app.cell
def _(requests):
    import xml.etree.ElementTree as ET

    def fetch_pubmed_metadata(pmids):
        BATCH_SIZE = 50
        records = []

        for i in range(0, len(pmids), BATCH_SIZE):
            batch = pmids[i:i+BATCH_SIZE]
            ids_str = ','.join(batch)
            url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            params = {
                "db": "pubmed",
                "id": ids_str,
                "retmode": "xml"
            }

            response = requests.get(url, params=params)
            root = ET.fromstring(response.content)

            for article in root.findall('.//PubmedArticle'):
                try:
                    title = article.findtext('.//ArticleTitle')
                    abstract = ' '.join([a.text for a in article.findall('.//AbstractText') if a.text])
                    year = article.findtext('.//PubDate/Year') or "NA"
                    pmid = article.findtext('.//PMID')
                    records.append({
                        "pmid": pmid,
                        "title": title,
                        "abstract": abstract,
                        "year": year,
                        "label": None  # For screening later
                    })
                except Exception as e:
                    print(f"Skipping article due to error: {e}")
                    continue

        return records
    return (fetch_pubmed_metadata,)


@app.cell
def _(fetch_pubmed_metadata, ids):
    import pandas as pd

    metadata = fetch_pubmed_metadata(ids)
    df = pd.DataFrame(metadata)
    print(df.head())

    return (df,)


@app.cell
def _(df, keywords):
    # let's try to calculate the revelance score:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    query = keywords.strip("AND")
    corpus = df['title'].fillna('').tolist()
    texts = [query] + corpus

    vectorizer = TfidfVectorizer(stop_words='english')
    X = vectorizer.fit_transform(texts)
    query_vec = X[0]
    abstract_vec = X[1:]

    similarities = cosine_similarity(query_vec, abstract_vec).flatten()
    df['rev_score']  = similarities
    df
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
