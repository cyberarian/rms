import streamlit as st
import sqlite3
from datetime import datetime
import pandas as pd
import os
from werkzeug.utils import secure_filename
import base64

# Set the page layout to wide
st.set_page_config(layout="wide")

# Constants
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {'pdf', 'xlsx', 'docx', 'jpg', 'png'}

# Create upload directory if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Database setup
def init_db():
    conn = sqlite3.connect('document_management.db')
    c = conn.cursor()
    
    # First, check if the file columns exist
    cursor = conn.execute('PRAGMA table_info(documents)')
    columns = [row[1] for row in cursor.fetchall()]
    
    # If the documents table exists but doesn't have the new columns
    if 'documents' in [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]:
        if 'file_paths' not in columns:
            c.execute('ALTER TABLE documents ADD COLUMN file_paths TEXT')
        if 'file_names' not in columns:
            c.execute('ALTER TABLE documents ADD COLUMN file_names TEXT')
    else:
        # Create the documents table with all columns
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
                      file_paths TEXT,
                      file_names TEXT,
                      FOREIGN KEY (department_id) REFERENCES departments (id),
                      FOREIGN KEY (project_id) REFERENCES projects (id),
                      FOREIGN KEY (archive_code_id) REFERENCES archive_codes (id))''')
    
    # Create other tables if they don't exist
    c.execute('''CREATE TABLE IF NOT EXISTS departments
                 (id INTEGER PRIMARY KEY, name TEXT UNIQUE)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS projects
                 (id INTEGER PRIMARY KEY, name TEXT UNIQUE)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS archive_codes
                 (id INTEGER PRIMARY KEY, code TEXT UNIQUE)''')
    
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

def save_uploaded_files(files):
    if not files:
        return [], []
    
    saved_paths = []
    saved_names = []
    
    for file in files:
        if file and allowed_file(file.name):
            filename = secure_filename(file.name)
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            
            # Save the file
            with open(file_path, "wb") as f:
                f.write(file.getbuffer())
            
            saved_paths.append(file_path)
            saved_names.append(filename)
    
    return saved_paths, saved_names

def create_document():
    conn = get_db()
    
    try:
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
        
        # File upload
        uploaded_files = st.file_uploader("Upload Files", 
                                        accept_multiple_files=True,
                                        type=list(ALLOWED_EXTENSIONS))
        
        if st.button("Add Document"):
            # Save uploaded files
            saved_paths, saved_names = save_uploaded_files(uploaded_files)
            
            c = conn.cursor()
            c.execute('''
                INSERT INTO documents 
                (title, file_title, description, doc_date, end_date,
                 doc_number, alt_number, department_id, project_id,
                 archive_code_id, security_class, status, created_at,
                 file_paths, file_names)
                VALUES (?, ?, ?, ?, ?, ?, ?, 
                        (SELECT id FROM departments WHERE name = ?),
                        (SELECT id FROM projects WHERE name = ?),
                        (SELECT id FROM archive_codes WHERE code = ?),
                        ?, ?, ?, ?, ?)
            ''', (title, file_title, description, doc_date, end_date,
                  doc_number, alt_number, department, project, archive_code,
                  security_class, status, datetime.now(),
                  "|".join(saved_paths) if saved_paths else "",
                  "|".join(saved_names) if saved_names else ""))
            
            conn.commit()
            st.success("Document successfully added!")
            
    except Exception as e:
        st.error(f"Error: {str(e)}")
    finally:
        conn.close()

def read_documents():
    conn = get_db()
    
    try:
        # Get documents with related data
        query = '''
            SELECT 
                d.id,
                d.title,
                d.file_title,
                d.description,
                d.doc_date,
                d.end_date,
                d.doc_number,
                d.alt_number,
                d.security_class,
                d.status,
                d.created_at,
                dept.name as department_name,
                p.name as project_name,
                ac.code as archive_code
            FROM documents d
            LEFT JOIN departments dept ON d.department_id = dept.id
            LEFT JOIN projects p ON d.project_id = p.id
            LEFT JOIN archive_codes ac ON d.archive_code_id = ac.id
            ORDER BY d.id DESC
        '''
        
        df = pd.read_sql(query, conn)
        
        if df.empty:
            st.warning("No documents found in the database")
            return
            
        # Display filters in columns
        col1, col2, col3 = st.columns(3)
        
        with col1:
            dept_filter = st.selectbox(
                "Filter by Department",
                ["All"] + sorted(df['department_name'].unique().tolist()),
                index=0
            )
            
        with col2:
            project_filter = st.selectbox(
                "Filter by Project",
                ["All"] + sorted(df['project_name'].unique().tolist()),
                index=0
            )
            
        with col3:
            status_filter = st.selectbox(
                "Filter by Status",
                ["All"] + sorted(df['status'].unique().tolist()),
                index=0
            )
        
        # Apply filters
        filtered_df = df.copy()
        
        if dept_filter != "All":
            filtered_df = filtered_df[filtered_df['department_name'] == dept_filter]
        if project_filter != "All":
            filtered_df = filtered_df[filtered_df['project_name'] == project_filter]
        if status_filter != "All":
            filtered_df = filtered_df[filtered_df['status'] == status_filter]
        
        # Format dates
        filtered_df['doc_date'] = pd.to_datetime(filtered_df['doc_date']).dt.strftime('%Y-%m-%d')
        filtered_df['end_date'] = pd.to_datetime(filtered_df['end_date']).dt.strftime('%Y-%m-%d')
        filtered_df['created_at'] = pd.to_datetime(filtered_df['created_at']).dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # Reorder and rename columns for display
        display_columns = {
            'title': 'Title',
            'file_title': 'File Title',
            'description': 'Description',
            'doc_date': 'Document Date',
            'end_date': 'End Date',
            'doc_number': 'Document Number',
            'alt_number': 'Alternative Number',
            'department_name': 'Department',
            'project_name': 'Project',
            'archive_code': 'Archive Code',
            'security_class': 'Security Class',
            'status': 'Status',
            'created_at': 'Created At'
        }
        
        # Select and rename columns for display
        display_df = filtered_df[display_columns.keys()].rename(columns=display_columns)
        
        # Add record count
        st.write(f"Total Records: {len(display_df)}")
        
        # Display the dataframe
        st.dataframe(
            display_df,
            hide_index=True,
            use_container_width=True
        )
        
        # Add export functionality
        if not display_df.empty:
            csv = display_df.to_csv(index=False)
            st.download_button(
                label="Export to CSV",
                data=csv,
                file_name="documents_export.csv",
                mime="text/csv",
            )
        
    except Exception as e:
        st.error(f"Error reading documents: {str(e)}")
    finally:
        conn.close()
        
def update_document():
    conn = get_db()
    success_update = False  # Flag to track successful update
    
    try:
        query = '''
            SELECT 
                d.id,
                d.title,
                d.file_title,
                d.description,
                d.doc_date,
                d.end_date,
                d.doc_number,
                d.alt_number,
                d.security_class,
                d.status,
                dept.name as department_name,
                p.name as project_name,
                ac.code as archive_code
            FROM documents d
            LEFT JOIN departments dept ON d.department_id = dept.id
            LEFT JOIN projects p ON d.project_id = p.id
            LEFT JOIN archive_codes ac ON d.archive_code_id = ac.id
            ORDER BY d.id DESC
        '''
        
        documents_df = pd.read_sql(query, conn)
        
        if documents_df.empty:
            st.warning("No documents found in the database")
            return
            
        documents_df['display_title'] = documents_df.apply(
            lambda x: f"{x['title']} - {x['department_name']} ({x['project_name']})", 
            axis=1
        )
        
        selected_display_title = st.selectbox(
            "Select Document to Update",
            options=documents_df['display_title'].tolist(),
            index=None,
            placeholder="Choose a document to update..."
        )
        
        if selected_display_title:
            selected_doc = documents_df[documents_df['display_title'] == selected_display_title].iloc[0]
            
            departments = pd.read_sql('SELECT * FROM departments', conn)
            projects = pd.read_sql('SELECT * FROM projects', conn)
            archive_codes = pd.read_sql('SELECT * FROM archive_codes', conn)
            
            with st.form("update_document_form"):
                st.write("### Update Document Details")
                
                new_title = st.text_input("Title", value=selected_doc['title'])
                new_file_title = st.text_input("File Title", value=selected_doc['file_title'])
                new_description = st.text_area("Description", value=selected_doc['description'])
                new_doc_number = st.text_input("Document Number", value=selected_doc['doc_number'])
                new_alt_number = st.text_input("Alternative Number", value=selected_doc['alt_number'])
                
                new_doc_date = st.date_input("Document Date", 
                                           value=pd.to_datetime(selected_doc['doc_date']).date())
                new_end_date = st.date_input("End Date", 
                                           value=pd.to_datetime(selected_doc['end_date']).date())
                
                dept_index = departments[departments['name'] == selected_doc['department_name']].index[0]
                proj_index = projects[projects['name'] == selected_doc['project_name']].index[0]
                code_index = archive_codes[archive_codes['code'] == selected_doc['archive_code']].index[0]
                
                new_department = st.selectbox("Department", 
                                            options=departments['name'].tolist(),
                                            index=int(dept_index))
                
                new_project = st.selectbox("Project", 
                                         options=projects['name'].tolist(),
                                         index=int(proj_index))
                
                new_archive_code = st.selectbox("Archive Code", 
                                              options=archive_codes['code'].tolist(),
                                              index=int(code_index))
                
                security_options = ["Biasa/Umum/Terbuka", "Terbatas"]
                status_options = ["Disetujui", "Versi Akhir", 
                                "Diterbitkan untuk Konstruksi", "As Built"]
                
                new_security_class = st.selectbox("Security Classification",
                                                options=security_options,
                                                index=security_options.index(selected_doc['security_class']))
                
                new_status = st.selectbox("Status",
                                        options=status_options,
                                        index=status_options.index(selected_doc['status']))
                
                submit_button = st.form_submit_button("Update Document")
                
                if submit_button:
                    try:
                        update_query = '''
                            UPDATE documents 
                            SET title = ?,
                                file_title = ?,
                                description = ?,
                                doc_date = ?,
                                end_date = ?,
                                doc_number = ?,
                                alt_number = ?,
                                department_id = (SELECT id FROM departments WHERE name = ?),
                                project_id = (SELECT id FROM projects WHERE name = ?),
                                archive_code_id = (SELECT id FROM archive_codes WHERE code = ?),
                                security_class = ?,
                                status = ?
                            WHERE id = ?
                        '''
                        
                        c = conn.cursor()
                        c.execute(update_query, (
                            new_title,
                            new_file_title,
                            new_description,
                            new_doc_date,
                            new_end_date,
                            new_doc_number,
                            new_alt_number,
                            new_department,
                            new_project,
                            new_archive_code,
                            new_security_class,
                            new_status,
                            int(selected_doc['id'])
                        ))
                        
                        conn.commit()
                        success_update = True  # Set flag for successful update
                        
                    except Exception as e:
                        st.error(f"Error updating document: {str(e)}")
                        conn.rollback()
            
            # Outside the form
            if success_update:
                st.success("✅ Document successfully updated!")
                if st.button("Refresh Page"):
                    st.rerun()
    
    except Exception as e:
        st.error(f"Error loading documents: {str(e)}")
    finally:
        conn.close()

def delete_document():
    conn = get_db()
    
    try:
        # Simplified query to start with
        query = '''
            SELECT 
                d.id,
                d.title,
                dept.name as department_name,
                p.name as project_name
            FROM documents d
            LEFT JOIN departments dept ON d.department_id = dept.id
            LEFT JOIN projects p ON d.project_id = p.id
            ORDER BY d.id DESC
        '''
        
        documents_df = pd.read_sql(query, conn)
        
        if documents_df.empty:
            st.warning("No documents found in the database")
            return
            
        # Create a more informative display string for each document
        documents_df['display_title'] = documents_df.apply(
            lambda x: f"{x['title']} - {x['department_name']} ({x['project_name']})", 
            axis=1
        )
        
        # Display document selector
        selected_display_title = st.selectbox(
            "Select Document to Delete",
            options=documents_df['display_title'].tolist(),
            index=None,
            placeholder="Choose a document to delete..."
        )
        
        if selected_display_title:
            # Get the selected document details
            selected_doc = documents_df[documents_df['display_title'] == selected_display_title].iloc[0]
            
            # Show document details before deletion
            st.write("### Document Details")
            st.write(f"Title: {selected_doc['title']}")
            st.write(f"Department: {selected_doc['department_name']}")
            st.write(f"Project: {selected_doc['project_name']}")
            
            # Add a confirmation checkbox
            confirm_delete = st.checkbox("I confirm that I want to delete this document")
            
            if confirm_delete:
                if st.button("Delete Document", type="primary"):
                    try:
                        # Delete the database record
                        c = conn.cursor()
                        c.execute('DELETE FROM documents WHERE id = ?', (int(selected_doc['id']),))
                        conn.commit()
                        
                        st.success("✅ Document successfully deleted!")
                        
                        # Add a button to refresh the page
                        if st.button("Refresh Page"):
                            st.rerun()
                            
                    except Exception as e:
                        st.error(f"Error during deletion: {str(e)}")
                        conn.rollback()
    
    except Exception as e:
        st.error(f"Error loading documents: {str(e)}")
    finally:
        conn.close()
        
# Streamlit UI
def main():
    st.title("Records Management System")
    
    # Initialize database
    init_db()
    
    menu = ["Create", "Read", "Update", "Delete"]
    choice = st.selectbox("Operation", menu)
    
    if choice == "Create":
        st.subheader("Add New Document")
        create_document()
    elif choice == "Read":
        st.subheader("View Documents")
        read_documents()  # Existing function remains the same
    elif choice == "Update":
        st.subheader("Update Document")
        update_document()
    elif choice == "Delete":
        st.subheader("Delete Document")
        delete_document()

if __name__ == "__main__":
    main()