import streamlit as st
import psycopg2
import hashlib
import os
from dotenv import load_dotenv
from embedder import Embedder
from vector_db import VectorDB
from query import answer_query
from chunker import Chunker
import google.generativeai as genai

load_dotenv()

DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("DB_HOST")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

genai.configure(api_key=GOOGLE_API_KEY)

def get_db_connection():
    return psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_user(username, password):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        pw_hash = hash_password(password)
        cur.execute('SELECT id, role, name FROM "user" WHERE username = %s AND password_hash = %s', (username, pw_hash))
        user = cur.fetchone()
        conn.close()
        return user
    except Exception as e:
        st.error(f"DB Error: {e}")
        return None

def register_user(name, email, username, password, role='enduser'):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        pw_hash = hash_password(password)

        cur.execute("""
            INSERT INTO "user" (name, email, username, password_hash, role)
            VALUES (%s, %s, %s, %s, %s)
        """, (name, email, username, pw_hash, role))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Registration failed: {e}")
        return False

def add_document_to_db(title, text, user_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO document (title, source, added_by, processed)
            VALUES (%s, %s, %s, TRUE)
            RETURNING id
        """, (title, text, user_id))
        doc_id = cur.fetchone()[0]
        conn.commit()
        conn.close()
        return doc_id
    except Exception as e:
        st.error(f"Failed to save doc: {e}")
        return None

def delete_document_from_db(doc_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM document WHERE id = %s", (str(doc_id),))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Delete failed: {e}")
        return False

def delete_user_from_db(user_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('DELETE FROM "user" WHERE id = %s', (str(user_id),))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Delete user failed: {e}")
        return False

@st.cache_resource
def load_search_engine():
    embedder = Embedder()
    db = VectorDB(dimension=384)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, title, source FROM document")
        rows = cur.fetchall()
        
        all_chunks = []
        all_ids = []
        
        for row in rows:
            doc_uuid, title, text = row
            chunks = Chunker.chunk_text(text)
            for i, chunk in enumerate(chunks):
                all_chunks.append(chunk)
                all_ids.append(f"{title}|{doc_uuid}|{i}")
        
        if all_chunks:
            db.add_vectors(embedder, all_chunks, all_ids)
            print(f"Loaded {len(all_chunks)} chunks from SQL.")
        
        conn.close()
    except Exception as e:
        st.warning(f"Could not load documents from DB: {e}")

    return db, embedder

st.set_page_config(page_title="Wikinews System", layout="wide")

if 'user_id' not in st.session_state:
    st.session_state['user_id'] = None
    st.session_state['role'] = None
    st.session_state['name'] = None

st.sidebar.title("Navigation")

if st.session_state['user_id']:
    st.sidebar.success(f"Welcome, {st.session_state['name']}")
    if st.sidebar.button("Logout"):
        st.session_state['user_id'] = None
        st.session_state['role'] = None
        st.rerun()
    
    options = ["Search"]
    if st.session_state['role'] in ['admin', 'curator']:
        options.append("Curator Dashboard")
    if st.session_state['role'] == 'admin':
        options.append("Admin Dashboard")
        
    choice = st.sidebar.radio("Go to:", options)
    
else:
    choice = st.sidebar.radio("Go to:", ["Login", "Sign Up"])

if choice == "Login":
    st.title("Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Log In"):
        user = verify_user(username, password)
        if user:
            st.session_state['user_id'] = user[0]
            st.session_state['role'] = user[1]
            st.session_state['name'] = user[2]
            st.success("Logged in successfully!")
            st.rerun()
        else:
            st.error("Invalid credentials")

elif choice == "Sign Up":
    st.title("Create Account")
    new_name = st.text_input("Full Name")
    new_email = st.text_input("Email")
    new_user = st.text_input("Username")
    new_pass = st.text_input("Password", type="password")

    admin_code = st.text_input("Admin Code (Optional)", type="password")
    
    if st.button("Register"):
        if admin_code == "CS480_SECRET":
            user_role = 'admin'
        else:
            user_role = 'enduser'
            
        if register_user(new_name, new_email, new_user, new_pass, role=user_role):
            st.success(f"Account created as {user_role}! Please log in.")
        else:
            st.error("Registration failed (Username/Email might exist).")
elif choice == "Search":
    st.title("🤖 Wikinews Search")
    
    db, embedder = load_search_engine()
    
    user_query = st.text_input("Ask a question:")
    if st.button("Search") and user_query:
        query_id = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("INSERT INTO querylog (user_id, query_text) VALUES (%s, %s) RETURNING id", 
                        (st.session_state['user_id'], user_query))
            query_id = cur.fetchone()[0]
            conn.commit()
            conn.close()
        except:
            pass

        results_data = db.query(embedder, user_query, n_results=3)
        results = results_data["documents"]
        result_ids = results_data["ids"]
    
        if query_id:
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                doc_ids = set()
                for result_id in result_ids:
                    parts = result_id.split('|')
                    if len(parts) >= 2:
                        doc_ids.add(parts[1])
                for doc_id in doc_ids:
                    cur.execute("INSERT INTO queryretrieval (query_id, document_id) VALUES (%s, %s)", 
                               (query_id, doc_id))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"Failed to log query retrieval: {e}")
        
        # print(f'results is {type(results)}: {results}')
        # context = "\n".join([res['text'] for res in results]) if results else ""
        context = "\n".join(results) if results else ""
        prompt = f"Context: {context}\n\nQuestion: {user_query}\nAnswer:"
        
        try:
            model = genai.GenerativeModel('models/gemini-2.0-flash')
            response = model.generate_content(prompt)
            st.write(response.text)
        except Exception as e:
            st.error(f"AI Error: {e}")
            
        st.subheader("Sources")
        for res in results:
            with st.expander(f"Read Source"):
                # st.write(res['text'])
                st.write(res)

elif choice == "Curator Dashboard":
    st.title("📂 Curator Dashboard")
    
    st.subheader("Upload New Document")
    doc_title = st.text_input("Document Title")
    doc_text = st.text_area("Document Text / Content")
    
    if st.button("Upload Document"):
        if doc_title and doc_text:
            new_id = add_document_to_db(doc_title, doc_text, st.session_state['user_id'])
            if new_id:
                db, embedder = load_search_engine()
                chunks = Chunker.chunk_text(doc_text)
                ids = [f"{doc_title}|{new_id}|{i}" for i in range(len(chunks))]
                db.add_vectors(embedder, chunks, ids)
                st.success("Document uploaded and indexed!")
                st.cache_resource.clear()
        else:
            st.warning("Please fill in title and text.")

    st.divider()
    st.subheader("Manage Documents")
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, title, created_at FROM document ORDER BY created_at DESC")
    docs = cur.fetchall()
    conn.close()
    
    for doc in docs:
        col1, col2 = st.columns([4, 1])
        col1.text(f"{doc[1]} (ID: {doc[0]})")
        if col2.button("Delete", key=doc[0]):
            if delete_document_from_db(doc[0]):
                st.success("Deleted!")
                st.cache_resource.clear()
                st.rerun()

elif choice == "Admin Dashboard":
    st.title("🛡️ Admin Dashboard")
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT id, name, email, role FROM "user"')
    users = cur.fetchall()
    
    for u in users:
        col1, col2 = st.columns([4, 1])
        
        with col1:
            with st.expander(f"{u[1]} ({u[3]})"):
                new_role = st.selectbox("Role", ["admin", "curator", "enduser"], 
                                       index=["admin", "curator", "enduser"].index(u[3]), 
                                       key=f"role_{u[0]}")
                if st.button("Update Role", key=f"btn_{u[0]}"):
                    cur.execute('UPDATE "user" SET role = %s WHERE id = %s', (new_role, u[0]))
                    conn.commit()
                    st.success("Updated!")
                    st.rerun()
        
        if col2.button("Delete", key=f"del_{u[0]}"):
            if delete_user_from_db(u[0]):
                st.success("User deleted!")
                st.rerun()
    conn.close()