"""User management interface for admin panel"""
import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

def init_user_db():
    """Initialize the user database"""
    conn = sqlite3.connect('admin_users.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_login DATETIME,
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    conn.commit()
    conn.close()

def render_user_management():
    """Render the user management interface"""
    st.header("👥 User Management")
    
    # Initialize database
    init_user_db()
    
    # Tabs for different user management functions
    tab1, tab2, tab3 = st.tabs(["User List", "Add User", "Audit Log"])
    
    with tab1:
        st.subheader("Current Users")
        try:
            conn = sqlite3.connect('admin_users.db')
            users_df = pd.read_sql_query("SELECT id, username, role, created_at, last_login, is_active FROM users", conn)
            if not users_df.empty:
                st.dataframe(users_df)
            else:
                st.info("No users found. Add users using the 'Add User' tab.")
        except Exception as e:
            st.error(f"Error loading users: {str(e)}")
        finally:
            conn.close()
    
    with tab2:
        st.subheader("Add New User")
        with st.form("add_user_form"):
            new_username = st.text_input("Username")
            new_password = st.text_input("Password", type="password")
            role = st.selectbox(
                "Role",
                ["Admin", "Editor", "Viewer"]
            )
            
            if st.form_submit_button("Add User"):
                try:
                    conn = sqlite3.connect('admin_users.db')
                    c = conn.cursor()
                    c.execute(
                        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                        (new_username, new_password, role)
                    )
                    conn.commit()
                    st.success(f"User {new_username} added successfully!")
                except sqlite3.IntegrityError:
                    st.error("Username already exists!")
                except Exception as e:
                    st.error(f"Error adding user: {str(e)}")
                finally:
                    conn.close()
    
    with tab3:
        st.subheader("User Activity Log")
        # Sample audit log data
        audit_data = {
            'timestamp': [datetime.now()],
            'user': ['admin'],
            'action': ['Viewed user management']
        }
        audit_df = pd.DataFrame(audit_data)
        st.dataframe(audit_df)
