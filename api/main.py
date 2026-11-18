
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from langgraph.graph import StateGraph
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI

from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import sessionmaker, declarative_base

from dotenv import load_dotenv
from pydantic import BaseModel
from typing import TypedDict
import os




load_dotenv()

database_url = os.getenv("database_url")

engine = create_engine(
    database_url,
    connect_args={"check_same_thread": False}
)

sessionLocal = sessionmaker(
    autoflush=False,
    autocommit=False,
    bind=engine
)

Base = declarative_base()


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)


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
    model="llama-3.3-70b-versatile",
    base_url="https://api.groq.com/openai/v1",
    api_key=os.getenv("GROQ_API_KEY")
)




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
                page_content=f"Title: {note.title}\nDescription: {note.description}",
                metadata={"id": note.id}
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
        search_kwargs={"k": 3}
    )

    relevant_docs = retriever.invoke(state["qs"])

    ct = "\n".join(
        [d.page_content for d in relevant_docs]
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
    Answer the question using the following notes.

    Context:
    {ct}

    Question:
    {qs}

    

    Give a clear answer.
    """

    res = llm.invoke(prompt)

    return {
        "ot": res.content
    }




graph = StateGraph(state)

graph.add_node("ragNode", ragNode)
graph.add_node("llmNode", llmNode)

graph.set_entry_point("ragNode")

graph.add_edge("ragNode", "llmNode")

app_graph = graph.compile()




app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True
)




@app.post("/notes")
def create_note(req: NoteRequest):

    db = sessionLocal()

    try:
        new_note = Note(
            title=req.title,
            description=req.description
        )

        db.add(new_note)
        db.commit()
        db.refresh(new_note)

        return {
            "id": new_note.id,
            "title": new_note.title,
            "description": new_note.description
        }

    finally:
        db.close()




@app.get("/notes")
def get_notes():

    db = sessionLocal()

    try:
        notes = db.query(Note).all()

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
