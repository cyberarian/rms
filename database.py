import streamlit as st
import sqlite3
from datetime import datetime
import pandas as pd

# Database setup
def init_db():
    conn = sqlite3.connect('document_management.db')
    c = conn.cursor()
    
    # Create tables
    c.execute('''CREATE TABLE IF NOT EXISTS departments
                 (id INTEGER PRIMARY KEY, name TEXT UNIQUE)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS projects
                 (id INTEGER PRIMARY KEY, name TEXT UNIQUE)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS archive_codes
                 (id INTEGER PRIMARY KEY, code TEXT UNIQUE)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS documents
                 (id INTEGER PRIMARY KEY,
                  title TEXT,
                  file_title TEXT,
                  description TEXT,
                  doc_date DATE,
                  end_date DATE,
                  doc_number TEXT,
                  alt_number TEXT,
                  department_id INTEGER,
                  project_id INTEGER,
                  archive_code_id INTEGER,
                  security_class TEXT,
                  status TEXT,
                  created_at TIMESTAMP,
                  FOREIGN KEY (department_id) REFERENCES departments (id),
                  FOREIGN KEY (project_id) REFERENCES projects (id),
                  FOREIGN KEY (archive_code_id) REFERENCES archive_codes (id))''')
    
    # Insert initial data
    departments = [
        "Sekretaris Perusahaan (SEP)", "Akuntansi dan Keuangan (AKK)",
        "Pengendalian dan Administrasi (PDA)", "Human Capital and General Affair (HCG)",
        "Supply Chain dan Peralatan (SCP)", "Satuan Pengawas Internal (SPI)",
        "Pemasaran (PEM)", "Sistem dan Informasi Teknologi (SIT)",
        "Manajemen Risiko (MAR)", "Perencanaan Korporasi (PEK)",
        "Teknik dan Desain (TED)", "Quality, Health, Safety, Security (QHS)",
        "Infra (INF) Proyek (PRO)"
    ]
    
    c.executemany('INSERT OR IGNORE INTO departments (name) VALUES (?)',
                  [(d,) for d in departments])
    
    projects = [
        "TIP Medan - Binjai", "Medan - Binjai", "Binjai - Pangkalan Brandan",
        "Junction - Palindra", "Indralaya - Prabumulih", "Palembang - Indralaya",
        "Pekanbaru - Bangkinang", "TIP Pekanbaru - Dumai", "Pekanbaru Ringroad",
        "Bangkinang - Pangkalan", "TIP Bengkulu", "Bengkulu - Taba Penanjung",
        "TIP Bakauheni - Terbanggi Besar", "TBPPKA Dukon Non Dukon", "13 Departemen"
    ]
    
    c.executemany('INSERT OR IGNORE INTO projects (name) VALUES (?)',
                  [(p,) for p in projects])
    
    # Archive codes (truncated for brevity - add all codes similarly)
    archive_codes = [
        "PRO100", "PRO100.01", "PRO100.02", "PRO200", "PRO300", "PRO400",
        "PRO500", "PRO600"
    ]
    
    c.executemany('INSERT OR IGNORE INTO archive_codes (code) VALUES (?)',
                  [(a,) for a in archive_codes])
    
    conn.commit()
    conn.close()

def get_db():
    return sqlite3.connect('document_management.db')

# Streamlit UI
def main():
    st.title("Document Management System")
    
    # Initialize database
    init_db()
    
    # Sidebar menu
    menu = ["Create", "Read", "Update", "Delete"]
    choice = st.sidebar.selectbox("Operation", menu)
    
    if choice == "Create":
        st.subheader("Add New Document")
        create_document()
    elif choice == "Read":
        st.subheader("View Documents")
        read_documents()
    elif choice == "Update":
        st.subheader("Update Document")
        update_document()
    elif choice == "Delete":
        st.subheader("Delete Document")
        delete_document()

def create_document():
    conn = get_db()
    
    # Get lookup data
    departments = pd.read_sql('SELECT * FROM departments', conn)
    projects = pd.read_sql('SELECT * FROM projects', conn)
    archive_codes = pd.read_sql('SELECT * FROM archive_codes', conn)
    
    # Form inputs
    title = st.text_input("Title")
    file_title = st.text_input("File Title")
    description = st.text_area("Description")
    doc_date = st.date_input("Document Date")
    end_date = st.date_input("End Date")
    doc_number = st.text_input("Document Number")
    alt_number = st.text_input("Alternative Number")
    
    department = st.selectbox("Department", departments['name'])
    project = st.selectbox("Project", projects['name'])
    archive_code = st.selectbox("Archive Code", archive_codes['code'])
    
    security_class = st.selectbox("Security Classification", 
                                ["Biasa/Umum/Terbuka", "Terbatas"])
    status = st.selectbox("Status", 
                         ["Disetujui", "Versi Akhir", 
                          "Diterbitkan untuk Konstruksi", "As Built"])
    
    if st.button("Add Document"):
        try:
            c = conn.cursor()
            c.execute('''
                INSERT INTO documents 
                (title, file_title, description, doc_date, end_date,
                 doc_number, alt_number, department_id, project_id,
                 archive_code_id, security_class, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 
                        (SELECT id FROM departments WHERE name = ?),
                        (SELECT id FROM projects WHERE name = ?),
                        (SELECT id FROM archive_codes WHERE code = ?),
                        ?, ?, ?)
            ''', (title, file_title, description, doc_date, end_date,
                  doc_number, alt_number, department, project, archive_code,
                  security_class, status, datetime.now()))
            
            conn.commit()
            st.success("Document successfully added!")
        except Exception as e:
            st.error(f"Error: {str(e)}")
        finally:
            conn.close()

def read_documents():
    conn = get_db()
    
    # Get documents with related data
    query = '''
        SELECT d.*, 
               dept.name as department_name,
               p.name as project_name,
               ac.code as archive_code
        FROM documents d
        LEFT JOIN departments dept ON d.department_id = dept.id
        LEFT JOIN projects p ON d.project_id = p.id
        LEFT JOIN archive_codes ac ON d.archive_code_id = ac.id
    '''
    
    df = pd.read_sql(query, conn)
    
    # Display filters
    col1, col2, col3 = st.columns(3)
    with col1:
        dept_filter = st.selectbox("Filter by Department",
                                 ["All"] + df['department_name'].unique().tolist())
    with col2:
        project_filter = st.selectbox("Filter by Project",
                                    ["All"] + df['project_name'].unique().tolist())
    with col3:
        status_filter = st.selectbox("Filter by Status",
                                   ["All"] + df['status'].unique().tolist())
    
    # Apply filters
    if dept_filter != "All":
        df = df[df['department_name'] == dept_filter]
    if project_filter != "All":
        df = df[df['project_name'] == project_filter]
    if status_filter != "All":
        df = df[df['status'] == status_filter]
    
    st.dataframe(df)
    conn.close()

def update_document():
    conn = get_db()
    
    # Get document list
    documents = pd.read_sql('SELECT id, title FROM documents', conn)
    selected_doc = st.selectbox("Select Document to Update", 
                              documents['title'].tolist())
    
    if selected_doc:
        doc_id = documents[documents['title'] == selected_doc]['id'].iloc[0]
        doc = pd.read_sql(f'SELECT * FROM documents WHERE id = {doc_id}', 
                         conn).iloc[0]
        
        # Update form
        new_title = st.text_input("Title", doc['title'])
        new_file_title = st.text_input("File Title", doc['file_title'])
        new_description = st.text_area("Description", doc['description'])
        new_status = st.selectbox("Status", 
                                ["Disetujui", "Versi Akhir",
                                 "Diterbitkan untuk Konstruksi", "As Built"],
                                index=["Disetujui", "Versi Akhir",
                                      "Diterbitkan untuk Konstruksi",
                                      "As Built"].index(doc['status']))
        
        if st.button("Update Document"):
            try:
                c = conn.cursor()
                c.execute('''
                    UPDATE documents 
                    SET title=?, file_title=?, description=?, status=?
                    WHERE id=?
                ''', (new_title, new_file_title, new_description, 
                      new_status, doc_id))
                
                conn.commit()
                st.success("Document successfully updated!")
            except Exception as e:
                st.error(f"Error: {str(e)}")
            finally:
                conn.close()

def delete_document():
    conn = get_db()
    
    # Get document list
    documents = pd.read_sql('SELECT id, title FROM documents', conn)
    selected_doc = st.selectbox("Select Document to Delete", 
                              documents['title'].tolist())
    
    if selected_doc:
        doc_id = documents[documents['title'] == selected_doc]['id'].iloc[0]
        
        if st.button("Delete Document"):
            try:
                c = conn.cursor()
                c.execute('DELETE FROM documents WHERE id=?', (doc_id,))
                conn.commit()
                st.success("Document successfully deleted!")
            except Exception as e:
                st.error(f"Error: {str(e)}")
            finally:
                conn.close()

if __name__ == "__main__":
    main()