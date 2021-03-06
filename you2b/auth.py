# Standard libraries
import os
import requests
from random import randint
from pathlib import Path

# OAuth2
import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
from googleapiclient.discovery import build

# Flask imports
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)

# Login manager
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)

# Internal imports
from .user import User

# Configuration
TOTAL_SECRET_FILES = 1 # edit to number of json files available
SECRET_FILE_NUM = randint(1, TOTAL_SECRET_FILES)
SECRET_FILE_NAME = 'csf' + str(SECRET_FILE_NUM) + '.json'

CLIENT_SECRETS_FILE = os.path.join(os.path.dirname(__file__), SECRET_FILE_NAME) # changes from the whole thing
SCOPES = ['https://www.googleapis.com/auth/youtube.readonly']
API_SERVICE_NAME = 'youtube'
API_VERSION = 'v3'

def credentials_to_dict(credentials):
    return {'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes}

bp = Blueprint('auth', __name__, url_prefix='/')

@bp.route("/login")
def login():
    # Create flow instance to manage the OAuth 2.0 Authorization Grant Flow steps.
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE, scopes=SCOPES)

    flow.redirect_uri = 'https://you2bflaskapp.herokuapp.com/login/callback' #changes from ...127...

    authorization_url, state = flow.authorization_url(
        # Enable offline access so that you can refresh an access token without
        # re-prompting the user for permission. Recommended for web server apps.
        access_type='offline',
        # Enable incremental authorization. Recommended as a best practice.
        include_granted_scopes='true')

    # Store the state so the callback can verify the auth server response.
    session['state'] = state

    return redirect(authorization_url)

@bp.route("/login/callback")
def oauth2callback():
    # Specify the state when creating the flow in the callback so that it can
    # verified in the authorization server response.
    state = session['state']

    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, state=state)
    flow.redirect_uri = url_for('auth.oauth2callback', _external=True)

    # Use the authorization server's response to fetch the OAuth 2.0 tokens.
    authorization_response = request.url
    flow.fetch_token(authorization_response=authorization_response)

    # Store credentials in the session.
    # ACTION ITEM: In a production app, you likely want to save these
    #              credentials in a persistent database instead.
    credentials = flow.credentials
    session['credentials'] = credentials_to_dict(credentials)
    
    youtube = build(API_SERVICE_NAME, API_VERSION, credentials=credentials)
    
    response = youtube.channels().list(part='id,snippet', mine=True).execute()
    if 'items' in response:
        channel = response['items']
        unique_id = channel[0]['id']
        profile_pic = channel[0]['snippet']['thumbnails']['default']['url']
        
        # If the user doesn't exist, add it to the database
        if not User.get(unique_id):
            User.create(unique_id, profile_pic)
        
        # Either way, collect the user from the database
        user = User.get(unique_id)
        login_user(user)
        return redirect(url_for('index'))
    else:
        return redirect(url_for('auth.error'))

@bp.route("/login/error")
def error():
    # The accounted that attempted to log in didn't work, so revoke its
    # credentials so the user can try again with a different account.
    if 'credentials' in session:
        credentials = google.oauth2.credentials.Credentials(**session['credentials'])
        revoke = requests.post('https://oauth2.googleapis.com/revoke',
        params = {'token': credentials.token},
        headers = {'content-type': 'application/x-www-form-urlencoded'})
    return (
        '<p>The YouTube account you attempted to log in with does not have an '
        'associated channel. Please <a class="button" href="/login">log in</a> '
        'with an account with an associated channel.</p>'
    )

@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))