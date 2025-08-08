# -*- coding: utf-8 -*-
{ 
    'name': 'Project Task Calendar View',
    'summary': 'Enhances the Calendar View of Project Task by displaying tasks with Project',
    'description': """
This module customizes the Calendar View of the Project Task model by displaying tasks with the Project Name.
    """,
    'version': '17.0.1.0.0',
    'license': 'AGPL-3',
    'author': 'Arionyx Solutions',
    'company': 'Arionyx Solutions',
    'category': 'Services/Project',
    'depends': ['project'],
    'data': [],
    'assets': {
        'web.assets_backend': [
            'project_task_calendar_view/static/src/js/**/*',
            'project_task_calendar_view/static/src/xml/**/*',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    "images": ['static/description/icon.png', 'static/description/screenshot1.png'],
}
