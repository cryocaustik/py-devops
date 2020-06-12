import os
import time
from azure.devops.connection import Connection
from azure.devops.exceptions import AzureDevOpsClientRequestError
from msrest.authentication import BasicAuthentication
from dotenv import load_dotenv
from dataclasses import dataclass

load_dotenv()


@dataclass
class Project:
    name: str
    description: str = ""
    sourceControlType: str = os.getenv("SOURCE_CONTROL_TYPE")
    templateTypeId: str = os.getenv("TEMPLATE_TYPE_ID")

    def serialize(self):
        if not self.sourceControlType:
            raise ValueError(
                f"Invalid value for sourceControlType: {self.sourceControlType}"
            )
        if not self.templateTypeId:
            raise ValueError(f"Invalid value for templateTypeId: {self.templateTypeId}")

        return {
            "name": self.name,
            "description": self.description,
            "capabilities": {
                "versioncontrol": {"sourceControlType": self.sourceControlType},
                "processTemplate": {"templateTypeId": self.templateTypeId},
            },
        }


@dataclass
class Repository:
    name: str
    project_id: str = None
    project_name: str = None

    def serialize(self):
        if not (self.project_id or self.project_name):
            raise ValueError("Repository Dataclass is missing a Project ID or Name")

        repository = {"name": self.name, "project": {}}
        if self.project_id:
            repository["project"]["id"] = self.project_id

        if self.project_name:
            repository["project"]["name"] = self.project_name

        return repository


class DevOps:
    """Azure DevOps REST API Client for quickly finding and creating projects and repositories.

    Kwargs:
        personal_access_token (str): Azure DevOps Personal Access Token for authentication. Default is pulled from .env file.
        org_name (str): Name of the organization to be used in Azure DevOps. Default is pulled from .env file.
        org_url (str): Full URL for the organization in Azure DevOps.  Default is pulled from .env file.
    """

    devops_base_url = "https://dev.azure.com/"
    core_client = None
    operation_client = None
    git_client = None

    def __init__(self, **kwargs):

        self.personal_access_token = kwargs.get(
            "personal_access_token", os.getenv("personal_access_token")
        )
        self.org_name = kwargs.get("org_name", os.getenv("org_name"))
        self.org_url = self.devops_base_url + self.org_name

    def get_authed_connection(self):
        """Get an authenticated Connection for Azure DevOps.

        Returns:
            class: Azure DevOps authenticated connected.
        """
        credentials = BasicAuthentication("", self.personal_access_token)
        return Connection(self.org_url, credentials)

    def get_core_client(self):
        """GEt an authenticated Client for Core endpoints.

        Returns:
            class: Azure DevOps authenticated Client for core endpoints.
        """
        if not self.core_client:
            connection = self.get_authed_connection()
            self.core_client = connection.clients.get_core_client()

        return self.core_client

    def get_operation_client(self):
        """Get an authenticated client for Operations endpoints.

        Returns:
            class: Azure DevOps authenticated Client for Operations endpoints.
        """
        if not self.operation_client:
            connection = self.get_authed_connection()
            self.operation_client = connection.clients.get_operations_client()

        return self.operation_client

    def get_git_client(self):
        """Get an authenticated Client for Git endpoints.

        Returns:
            class: Azure DevOps authenticated Client for Git endpoints.
        """
        if not self.git_client:
            connection = self.get_authed_connection()
            self.git_client = connection.clients.get_git_client()

        return self.git_client

    def get_operation_status(self, id):
        """Get status of an operation.

        Args:
            id (str): ID of Azure DevOps operation.

        Returns:
            str: Status of the operation.
        """
        client = self.get_operation_client()
        response = client.get_operation(id)

        return response.status

    def get_operation_valid_status(self, id, max_wait=30, sleep=10):
        """Attempt to get a successful status for an operation in given amount of time, as defined by max_wait.

        Args:
            id (str): Azure DevOps Operation ID.
            max_wait (int, optional): Maximum seconds to attempt requests for. Defaults to 30.
            sleep (int, optional): Seconds to wait in-between requests. Defaults to 10.

        Returns:
            str: Status of Azure DevOps operation.
        """
        valid_statuses = ["succeeded", "cancelled", "failed"]
        st_time = time.time()
        status = self.get_operation_status(id)

        while status not in valid_statuses and time.time() - st_time < max_wait:
            print(f"we are waiting...{time.time() - st_time}", sep="\b")
            time.sleep(sleep)
            status = self.get_operation_status(id)

        return status

    def get_existing_projects(self):
        """Get a list of existing projects.

        Returns:
            list: List of Azure DevOps Project objects.
        """
        client = self.get_core_client()
        projects = dict()
        response = client.get_projects()
        while response:
            for p in response.value:
                projects[p.name] = p

            if response.continuation_token:
                response = client.get_projects(response.continuation_token)
            else:
                response = None

        return projects

    def get_project(self, project):
        """Get a Azure DevOps Project by ID or Name.

        Args:
            project (str): Project ID or Name.

        Returns:
            object: Azure DevOps Project object.
        """
        client = self.get_core_client()
        response = client.get_project(project)

        return response

    def find_or_create_project(self, project, confirm=True):
        """Find or create a Azure DevOps project using the Project ID or Name.

        Args:
            project (str): Project ID or Name.
            confirm (bool, optional): Attempt to confirm project creation. Defaults to True.

        Raises:
            Exception: Project operation status is unable to be determined and likely failed.
                This may also be caused a timeout in retreiving the creation operation status.

        Returns:
            object: Azure DevOps Project object.
        """
        existing_projects = self.get_existing_projects()
        if project.name in existing_projects:
            return existing_projects[project.name]

        client = self.get_core_client()
        response = client.queue_create_project(project.serialize())

        if not confirm:
            return response

        status = self.get_operation_valid_status(response.id)
        if status in ["cancelled", "failed"]:
            raise Exception(f"Project creation failed for : {project}")

        return self.get_project(project.name)

    def get_existing_repositories(self, project=None):
        """Get a list of existing repositories.

        Args:
            project (str, optional): Project ID or Name. Defaults to None.
        
        Returns:
            list: List of Azure DevOps Repository objects.
        """
        client = self.get_git_client()
        repositories = dict()
        response = client.get_repositories(project=project)

        # no repositories exist, return blank dict
        if response.count == 0:
            return repositories

        for r in response:
            repositories[r.name] = r

        return repositories

    def get_repository(self, id, project_id=None):
        """Get a Azure DevOps Repository by ID and (optional) project ID.

        Args:
            id (str): Repository ID.
            project_id (str, optional): Project ID. Defaults to None.

        Returns:
            object: Azure DevOps Repository object.
        """
        client = self.get_git_client()

        return client.get_repository(id=id, project_id=project_id)

    def find_or_create_repository(self, repository, confirm=True):
        """Find or create a Azure DevOps Repository in specified Project.

        Args:
            repository (dataclass): Repository Dataclass.
            confirm (bool, optional): Attempt to confirm repository creation. Defaults to True.

        Raises:
            Exception: Repository operation status is unable to be determined and likely failed. 
                This may also be caused by a timeout in retreiving the creation operation status.
            
            Exception: Repository is not found in project repository list. 
                This could be due to an incomplete (still queued) or failed creation.

        Returns:
            object: Azure DevOps Repository object.
        """
        project = (
            repository.project_id if repository.project_id else repository.project_name
        )
        existing_repositories = self.get_existing_repositories(project)
        if repository.name in existing_repositories:
            return existing_repositories[repository.name]

        client = self.get_git_client()
        response = client.create_repository(repository.serialize())

        if not confirm:
            return response

        status = self.get_operation_valid_status(response.id)
        if status in ["cancelled", "failed"]:
            raise Exception(f"Repository creation failed for : {project}")

        existing_repositories = self.get_existing_repositories(project)
        if repository.name not in existing_repositories:
            raise Exception(
                f"Repository creation may have failed as it is not found in project {project}"
            )
        created_repository = existing_repositories[repository.name]

        return self.get_repository(created_repository.id, project)

