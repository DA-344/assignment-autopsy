"""
assignment_autopsy
~~~~~~~~~~~~~~~~~~

Assignment Autopsy is a school-focused, assignment management and analysis tool built in Python which provides
an easy-to-use and familiar UX for students and educators alike.

It takes in account security for all members by allowing features such as secure password hashing, session management,
and two-factor authentication.

The project aims to simplify the management and analysis of academic assignments while ensuring the security and privacy of its users.

It is divided in different modules, each handling a specific aspect of the application, such as security, session management, and assignment analysis:

- `security`: Handles password hashing, two-factor authentication, and other security-related features.
- `sessions`: Manages user sessions, including session creation, hashing, and expiration.
- `assignments`: Provides tools for managing and analyzing academic assignments.
- `workers`: Handles background tasks related to assignment evaluations.
- `database`: Contains the database models and schema definitions used throughout the application.
- `config`: Contains configuration settings and environment variables for the application.
- `templates`: Contains the HTML templates used for rendering the web interface.
- `static`: Contains static files such as CSS, JavaScript, and images used in the web interface.
- `services`: Contains service layer implementations for handling business logic and interactions between different modules.
- `i18n`: Handles internationalization and localization, including loading translation catalogs and determining the user's preferred language.
    It currently supports English and Spanish, though additional languages may be added by creating a folder in "locales" with the "<language 2-letter code>/LC_MESSAGES"
    structure, and placing the .po files within that folder and translating them accordingly.

This package is also built so it is as simple as configuring an environment file, and running `py -m assignment_autopsy` to start the application.
"""
