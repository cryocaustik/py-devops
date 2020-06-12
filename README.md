# py-devops

Simplified wrapper for Azure DevOps to find and/or create Projects and Repositories.


## Dependencies 

- [Python 3](https://www.python.org/)
- [azure-devops](https://github.com/microsoft/azure-devops-python-api)
- [python-dotenv](https://github.com/theskumar/python-dotenv)


## Usage

```python
>>> from devops import DevOps, Project
>>> d = DevOps()
>>> project = Project(name="Some Project")
>>> d.find_or_create_project(project)

<azure.devops.v5_1.core.models.TeamProject object at 0x000001E5F2DFED00>
```