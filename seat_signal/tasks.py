from background_task import background
import requests

# look at documentation to figure out django-background_tasks

@background(schedule=60)
def watch_task():
    pass

