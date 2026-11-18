import { useEffect, useState } from "react";
import "./App.scss";

const API_URL = "http://localhost:8000";

function App() {
  const [notes, setNotes] = useState([]);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [editId, setEditId] = useState(null);

  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  // Fetch all notes from MongoDB
  const fetchNotes = async () => {
    try {
      const response = await fetch(`${API_URL}/notes`);
      if (!response.ok) throw new Error("Failed to fetch notes");

      const data = await response.json();
      setNotes(data);
    } catch (error) {
      console.error(error);
    }
  };

  useEffect(() => {
    fetchNotes();
  }, []);

  // Add or update a note
  const handleSave = async (e) => {
    e.preventDefault();

    if (!title.trim() || !content.trim()) {
      alert("Please enter title and content");
      return;
    }

    setSaving(true);

    try {
      const url = editId ? `${API_URL}/notes/${editId}` : `${API_URL}/notes`;

      const response = await fetch(url, {
        method: editId ? "PUT" : "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ title, content }),
      });

      if (!response.ok) throw new Error("Unable to save note");

      setTitle("");
      setContent("");
      setEditId(null);

      await fetchNotes();
    } catch (error) {
      alert(error.message);
    } finally {
      setSaving(false);
    }
  };

  // Edit note
  const handleEdit = (note) => {
    setTitle(note.title);
    setContent(note.content);
    setEditId(note.id);

    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  // Delete note
  const handleDelete = async (id) => {
    if (!window.confirm("Are you sure you want to delete this note?")) {
      return;
    }

    try {
      const response = await fetch(`${API_URL}/notes/${id}`, {
        method: "DELETE",
      });

      if (!response.ok) throw new Error("Unable to delete note");

      await fetchNotes();
    } catch (error) {
      alert(error.message);
    }
  };

  // Ask AI using saved notes
  const handleAskAI = async (e) => {
    e.preventDefault();

    if (!question.trim()) return;

    setLoading(true);
    setAnswer("");

    try {
      const response = await fetch(`${API_URL}/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ question }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "AI request failed");
      }

      setAnswer(data.answer);
    } catch (error) {
      setAnswer(error.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <header className="header">
        <h1>Dhanushvardan's Notes</h1>
      </header>

      <main className="container">
        {/* Add Note */}
        <section className="section">
          <h2>{editId ? "Update Note" : "Add a Note"}</h2>

          <form className="note-form" onSubmit={handleSave}>
            <input
              type="text"
              placeholder="Enter note title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />

            <textarea
              placeholder="Write your note here..."
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows="5"
            />

            <div className="form-actions">
              <button type="submit" disabled={saving}>
                {saving ? "Saving..." : editId ? "Update Note" : "Add Note"}
              </button>

              {editId && (
                <button
                  type="button"
                  className="cancel-btn"
                  onClick={() => {
                    setTitle("");
                    setContent("");
                    setEditId(null);
                  }}
                >
                  Cancel
                </button>
              )}
            </div>
          </form>
        </section>

        {/* Display Notes */}
        <section className="section">
          <h2>My Notes ({notes.length})</h2>

          {notes.length === 0 ? (
            <p className="empty">No notes yet. Add your first note!</p>
          ) : (
            <div className="notes-list">
              {notes.map((note) => (
                <div className="note-card" key={note.id}>
                  <h3>{note.title}</h3>
                  <p>{note.content}</p>

                  <div className="note-footer">
                    <span>
                      {new Date(note.created_at).toLocaleDateString()}
                    </span>

                    <div>
                      <button
                        className="edit-btn"
                        onClick={() => handleEdit(note)}
                      >
                        Edit
                      </button>

                      <button
                        className="delete-btn"
                        onClick={() => handleDelete(note.id)}
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Ask AI */}
        <section className="section ai-section">
          <h2>Ask AI from My Notes</h2>

          <p className="ai-description">
            Ask questions about your saved notes. AI will find relevant
            information and answer you.
          </p>

          <form className="ai-form" onSubmit={handleAskAI}>
            <input
              type="text"
              placeholder="Example: What did I discuss about the project?"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
            />

            <button type="submit" disabled={loading}>
              {loading ? "Thinking..." : "Ask AI"}
            </button>
          </form>

          {answer && (
            <div className="answer-box">
              <h3>AI Answer</h3>
              <p>{answer}</p>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

export default App;
