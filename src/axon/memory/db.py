"""Firebase Firestore database initialisation.

This module owns the Firebase App lifecycle and provides the
Firestore async client. The rest of Axon accesses the database
through ``repositories.py``.
"""

import logging
import os

import firebase_admin
from firebase_admin import credentials, firestore_async
from google.cloud.firestore import AsyncClient

logger = logging.getLogger(__name__)


def init_firebase(
    project_id: str | None = None,
    cred_path: str | None = None,
) -> AsyncClient:
    """Initialise Firebase and return an async Firestore client.

    Credential resolution order:
    1. ``cred_path`` argument (absolute path preferred)
    2. ``GOOGLE_APPLICATION_CREDENTIALS`` environment variable
    3. Application Default Credentials (ADC)

    If the app is already initialised, it re-uses the existing app.

    Args:
        project_id: GCP project ID to bind the Firestore client to.
        cred_path: Absolute path to a service-account JSON file.

    Returns:
        An ``AsyncClient`` bound to the Firebase app.
    """
    if not firebase_admin._apps:
        logger.info("Initialising Firebase Admin app")
        options: dict[str, str] = {}
        if project_id:
            options["projectId"] = project_id

        # Prefer the explicitly supplied path; fall back to env var.
        resolved_cred = cred_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if resolved_cred and os.path.exists(resolved_cred):
            logger.info("Using service-account credentials: %s", resolved_cred)
            cred = credentials.Certificate(resolved_cred)
            firebase_admin.initialize_app(cred, options=options or None)
        else:
            if resolved_cred:
                logger.warning(
                    "Credential file not found at '%s'; falling back to ADC",
                    resolved_cred,
                )
            firebase_admin.initialize_app(options=options or None)

    return firestore_async.client()
