
import os
import re

from dotenv import load_dotenv
from typing import TypedDict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text
)

from sqlalchemy.orm import sessionmaker, declarative_base

from langgraph.graph import StateGraph, END

from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI


from url_reader import extract_url_content




load_dotenv()

database_url = os.getenv("database_url")
groq_api_key = os.getenv("api_key") or os.getenv("GROQ_API_KEY")

if not database_url:
    raise ValueError("database_url is missing in .env")

if not groq_api_key:
    raise ValueError("Groq API key is missing in .env")




engine = create_engine(
    database_url,
    pool_pre_ping=True
)

sessionLocal = sessionmaker(
    autoflush=False,
    autocommit=False,
    bind=engine
)

Base = declarative_base()




class Note(Base):

    __tablename__ = "noteDB"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True
    )

    title = Column(
        String(255),
        nullable=False
    )

    description = Column(
        Text,
        nullable=False
    )


Base.metadata.create_all(bind=engine)




class NoteRequest(BaseModel):
    title: str
    description: str


class qst(BaseModel):
    qst: str



class state(TypedDict):
    txt: str
    ct: str
    qs: str
    ot: str




embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/paraphrase-MiniLM-L3-v2"
)




llm = ChatOpenAI(
    model="openai/gpt-oss-20b",
    base_url="https://api.groq.com/openai/v1",
    api_key=groq_api_key,
    temperature=0
)



def find_urls(text: str):

    urls = re.findall(
        r'https?://[^\s<>"\']+',
        text
    )

    return list(dict.fromkeys(
        url.rstrip(".,;!?)\"]}")
        for url in urls
    ))




def ragNode(state: state):

    db = sessionLocal()

    try:

        notes = db.query(Note).all()

        if not notes:

            return {
                "txt": "",
                "ct": "",
                "qs": state["qs"]
            }

        docs = [
            Document(
                page_content=(
                    f"Title: {note.title}\n"
                    f"Description: {note.description}"
                ),
                metadata={
                    "id": note.id,
                    "title": note.title
                }
            )
            for note in notes
        ]

    finally:
        db.close()

    
    vectorstore = FAISS.from_documents(
        docs,
        embeddings
    )

    
    retriever = vectorstore.as_retriever(
        search_kwargs={"k": min(3, len(docs))}
    )

    relevant_docs = retriever.invoke(state["qs"])

    ct = "\n\n".join(
        [doc.page_content for doc in relevant_docs]
    )

    return {
        "txt": "",
        "ct": ct,
        "qs": state["qs"]
    }




def llmNode(state: state):

    ct = state["ct"]
    qs = state["qs"]

    if not ct:

        return {
            "ot": "No notes found. Please create notes first."
        }

    prompt = f"""


Answer the user's question using the retrieved notes
and extracted webpage content.



CONTEXT:

{ct}

USER QUESTION:

{qs}

ANSWER:
"""

    response = llm.invoke(prompt)

    return {
        "ot": response.content
    }



graph = StateGraph(state)

graph.add_node(
    "ragNode",
    ragNode
)

graph.add_node(
    "llmNode",
    llmNode
)

graph.set_entry_point("ragNode")

graph.add_edge(
    "ragNode",
    "llmNode"
)

graph.add_edge(
    "llmNode",
    END
)

app_graph = graph.compile()




app = FastAPI(
    title="AI Notes Application"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000"
        
    ],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True
)




@app.post("/notes")
async def create_note(req: NoteRequest):

    title = req.title.strip()
    description = req.description.strip()

    if not title:
        raise HTTPException(
            status_code=400,
            detail="Title cannot be empty"
        )

    if not description:
        raise HTTPException(
            status_code=400,
            detail="Description cannot be empty"
        )

    
    urls = find_urls(description)

    extracted_content = []

    
    for url in urls:

        result = await extract_url_content(url)

        if result.get("success"):

            extracted_content.append(
                f"""
--- EXTRACTED WEBPAGE CONTENT ---

Website Title:
{result.get('title', 'No title')}

Website URL:
{result.get('url', url)}

Description:
{result.get('content', '')}

--- END OF WEBPAGE CONTENT ---
"""
            )

        else:

            print(
                f"URL extraction failed: {url} - "
                f"{result.get('error', 'Unknown error')}"
            )

    
    if extracted_content:

        description += "\n\n" + "\n\n".join(
            extracted_content
        )

    db = sessionLocal()

    try:

        new_note = Note(
            title=title,
            description=description
        )

        db.add(new_note)
        db.commit()
        db.refresh(new_note)

        return {
            "id": new_note.id,
            "title": new_note.title,
            "description": new_note.description
        }

    except Exception as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Note creation failed: {str(e)}"
        )

    finally:
        db.close()




@app.get("/notes")
def get_notes():

    db = sessionLocal()

    try:

        notes = db.query(Note).order_by(
            Note.id.desc()
        ).all()

        return [
            {
                "id": note.id,
                "title": note.title,
                "description": note.description
            }
            for note in notes
        ]

    finally:
        db.close()




@app.get("/notes/{note_id}")
def get_note(note_id: int):

    db = sessionLocal()

    try:

        note = db.query(Note).filter(
            Note.id == note_id
        ).first()

        if not note:

            raise HTTPException(
                status_code=404,
                detail="Note not found"
            )

        return {
            "id": note.id,
            "title": note.title,
            "description": note.description
        }

    finally:
        db.close()




@app.put("/notes/{note_id}")
def update_note(
    note_id: int,
    req: NoteRequest
):

    db = sessionLocal()

    try:

        note = db.query(Note).filter(
            Note.id == note_id
        ).first()

        if not note:

            raise HTTPException(
                status_code=404,
                detail="Note not found"
            )

        if not req.title.strip() or not req.description.strip():

            raise HTTPException(
                status_code=400,
                detail="Title and description cannot be empty"
            )

        note.title = req.title.strip()
        note.description = req.description.strip()

        db.commit()
        db.refresh(note)

        return {
            "message": "Note updated successfully",
            "id": note.id,
            "title": note.title,
            "description": note.description
        }

    finally:
        db.close()




@app.delete("/notes/{note_id}")
def delete_note(note_id: int):

    db = sessionLocal()

    try:

        note = db.query(Note).filter(
            Note.id == note_id
        ).first()

        if not note:

            raise HTTPException(
                status_code=404,
                detail="Note not found"
            )

        db.delete(note)
        db.commit()

        return {
            "message": "Note deleted successfully"
        }

    finally:
        db.close()




@app.post("/askragai")
def askragAi(req: qst):

    if not req.qst.strip():

        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty"
        )

    try:

        res = app_graph.invoke({
            "qs": req.qst,
            "txt": "",
            "ct": "",
            "ot": ""
        })

        return {
            "question": req.qst,
            "answer": res["ot"]
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=f"AI processing failed: {str(e)}"
        )




@app.get("/")
def home():

    return {
        "message": "AI Notes API is running"
    }
