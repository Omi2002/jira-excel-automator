import streamlit as st
import pandas as pd
from jira import JIRA, JIRAError
import io
import os
from dotenv import load_dotenv

# --- Load Environment Variables ---
load_dotenv()

# Fetch defaults from .env file (if it exists)
DEFAULT_URL = os.getenv("JIRA_SERVER", "")
DEFAULT_EMAIL = os.getenv("JIRA_EMAIL", "")
DEFAULT_TOKEN = os.getenv("JIRA_API_TOKEN", "")
DEFAULT_PROJECT = os.getenv("PROJECT_KEY", "")

# --- Page Config ---
st.set_page_config(page_title="Jira Excel Automator", layout="wide")
st.title("🚀 Jira Task Automation Portal")
st.markdown("Upload your CSV to **Create** or **Update** Jira tasks automatically.")

# --- Sidebar: Configuration ---
with st.sidebar:
    st.header("🔑 Jira Configuration")
    
    # Only show input if the variable is NOT found in environment/secrets
    if not DEFAULT_URL:
        jira_url = st.text_input("Jira Server URL", placeholder="https://your-domain.atlassian.net")
    else:
        jira_url = DEFAULT_URL
        st.success("✅ Server URL Configured")

    if not DEFAULT_EMAIL:
        email = st.text_input("Email", placeholder="admin@company.com")
    else:
        email = DEFAULT_EMAIL
        st.success("✅ Email Configured")

    if not DEFAULT_TOKEN:
        api_token = st.text_input("API Token", type="password")
    else:
        api_token = DEFAULT_TOKEN
        st.success("✅ API Token Configured")

    if not DEFAULT_PROJECT:
        project_key = st.text_input("Project Key", placeholder="SB")
    else:
        project_key = DEFAULT_PROJECT
        st.success("✅ Project Key Configured")

    st.divider()
    if st.button("Clear Cache / Log Out"):
        st.rerun()
        
# --- Main UI ---
uploaded_file = st.file_uploader("Upload your CSV file", type=["csv"])

if uploaded_file is not None:
    # Read the CSV
    df = pd.read_csv(uploaded_file)
    st.subheader("Preview Data")
    st.dataframe(df.head())

    if st.button("Start Syncing to Jira"):
        if not (jira_url and email and api_token and project_key):
            st.error("Please fill in all credentials in the sidebar!")
        else:
            try:
                # Connect to Jira
                jira = JIRA(server=jira_url, basic_auth=(email, api_token))
                
                status_list = []
                progress_bar = st.progress(0)
                total_rows = len(df)

                for index, row in df.iterrows():
                    # Clean the data
                    issue_key = str(row['Issue key']).strip() if pd.notna(row['Issue key']) and str(row['Issue key']) != 'nan' else None
                    summary = str(row['Summary'])
                    
                    # Original Estimate (OE) - using Jira's internal timetracking logic
                    oe_value = str(row['Original estimate']) if pd.notna(row['Original estimate']) else None

                    # Build base dictionary
                    fields_dict = {
                        'project': {'key': project_key},
                        'summary': summary,
                        'priority': {'name': str(row['Priority'])},
                        'issuetype': {'name': str(row['Issue Type']) if pd.notna(row['Issue Type']) else 'Task'},
                    }
                    
                    # Add OE to dict if present
                    if oe_value:
                        fields_dict['timetracking'] = {'originalEstimate': oe_value}

                    try:
                        issue = None
                        # Check if we should update or create
                        if issue_key:
                            try:
                                issue = jira.issue(issue_key)
                            except JIRAError:
                                issue = None

                        if issue:
                            # --- UPDATE TASK ---
                            update_data = {
                                'summary': summary, 
                                'priority': {'name': str(row['Priority'])}
                            }
                            if oe_value:
                                update_data['timetracking'] = {'originalEstimate': oe_value}
                            
                            issue.update(fields=update_data)
                            result = f"✅ Row {index+1}: Updated {issue_key}"
                            current_issue = issue
                        else:
                            # --- CREATE TASK ---
                            new_issue = jira.create_issue(fields=fields_dict)
                            result = f"🆕 Row {index+1}: Created {new_issue.key}"
                            df.at[index, 'Issue key'] = new_issue.key # Update DF with new key
                            current_issue = new_issue

                        # --- HANDLE ASSIGNEE ---
                        assignee_id = row['Assignee Id'] if pd.notna(row['Assignee Id']) else None
                        if assignee_id:
                            jira.assign_issue(current_issue, assignee_id)
                        
                        status_list.append(result)

                    except Exception as e:
                        status_list.append(f"❌ Row {index+1} Error: {str(e)}")
                    
                    # Update progress
                    progress_bar.progress((index + 1) / total_rows)

                st.success("Sync Process Complete!")
                
                # Show individual row status in a scrollable box
                with st.expander("View Sync Logs"):
                    for s in status_list:
                        st.write(s)

                # --- DOWNLOAD UPDATED CSV ---
                st.divider()
                st.subheader("Download Results")
                output_csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download CSV with New Issue Keys",
                    data=output_csv,
                    file_name="synced_jira_tasks.csv",
                    mime="text/csv"
                )

            except Exception as e:
                st.error(f"Failed to connect to Jira. Check URL/Token. Error: {str(e)}")

# Footer
st.markdown("---")
st.caption("Jira Excel Automation Tool | March 2026")