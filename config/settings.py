# config/settings.py

BQ_PROJECT_ID = "haulmer-ucloud-production"
BQ_DATASET_ID = "Jira"

JIRA_SECRET_ID = "Jira"

FORCE_PROJECT_IN_JQL = True

BOARDS = {
    248: {
        "table": "CLO_Agenda_raw",
        "jira_project_key": "CLO",
        "etl_name": "CLO_Agenda",
        "batch_size": 100,
        "allow_cross_project": False,
    }
}
