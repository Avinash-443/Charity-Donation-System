from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
import pyrebase
from datetime import datetime, timedelta
import os
import uuid
from web3 import Web3
import math
from werkzeug.utils import secure_filename
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from fpdf import FPDF
from io import BytesIO
import pytz
import json

# Firebase Admin SDK - for Firestore
cred = credentials.Certificate(r"C:\College projects\3rd year\Introduction to Innovative projects\FinalImplementation\transparentcharitydonation-firebase-adminsdk-fbsvc-83f5ad650b.json")
firebase_admin.initialize_app(cred)
db = firestore.client()  # ✅ This is Firestore client

# Pyrebase config for Auth
firebaseConfig = {
    "apiKey": "AIzaSyAmD73u9Oy549jAkcziy9NirEKh1AmTr3w",
    "authDomain": "transparentcharitydonation.firebaseapp.com",
    "projectId": "transparentcharitydonation",
    "storageBucket": "transparentcharitydonation.appspot.com",  # 🔁 Fixed: should end with .appspot.com
    "messagingSenderId": "770050026083",
    "appId": "1:770050026083:web:f4922a83011e1f72b0a656",
    "measurementId": "G-103JFJYRX2",
    "databaseURL": ""  # Leave blank since we're using Firestore, not Realtime DB
}

firebase = pyrebase.initialize_app(firebaseConfig)
auth = firebase.auth()

app = Flask(__name__)
app.secret_key = "blockchain-charity-key"

# Ensure upload folder exists

#app.config['UPLOAD_FOLDER'] = 'static/uploads'
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# Routes

def date_diff(end_date_str):
    try:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        delta = (end_date - datetime.utcnow()).days
        return max(delta, 0)  # Avoid negative days
    except Exception as e:
        return "N/A"

# Register the filter with Jinja
app.jinja_env.filters['date_diff'] = date_diff

@app.route('/')
def home():
    return render_template('starting_page.html')

@app.route('/login_selection')
def login_selection():
    return render_template('login_selection.html')

@app.route('/auth_donors')
def auth_donors():
    return render_template('auth_donors.html')

@app.route('/auth_charity')
def auth_charity():
    return render_template('auth_charity.html')

@app.route('/auth_admin')
def auth_admin():
    return render_template('auth_admin.html')


# ==============================
# 🔷 Donor Auth + Firestore Save
# ==============================

@app.route('/donor_signup', methods=['POST'])
def donor_signup():
    name = request.form['name']
    email = request.form['email']
    password = request.form['password']
    phone = request.form['phone']

    try:
        user = auth.create_user_with_email_and_password(email, password)
        donorId = user['localId']
        

        # ✅ Save to Firestore
        db.collection("donors").document(donorId).set({
            "donorId": donorId,
            "name": name,
            "email": email,
            "phone": phone,
            "createdAt": datetime.now()
        })

        db.collection("donors_login").document(donorId).set({
            "donorId": donorId,
            "name": name,
            "email": email,
            "phone": phone,
            "createdAt": datetime.now()
        })

        return redirect('/donor_dashboard')

    except Exception as e:
        return f"Signup failed: {str(e)}"

@app.route('/donor_login', methods=['POST'])
def donor_login():
    email = request.form['email']
    password = request.form['password']

    try:
        # Sign in with email and password
        auth.sign_in_with_email_and_password(email, password)
        
        # Fetch donor's ID from the Firestore 'donors_login' collection using the email
        donor_ref = db.collection('donors_login').where('email', '==', email).limit(1)
        donor_doc = donor_ref.get()

        # Check if donor exists and get donorId
        if donor_doc:
            donor_data = donor_doc[0].to_dict()  # Assuming the document exists
            donor_id = donor_data.get('donorId')  # Get the donorId
            if donor_id:
                # Store user_email and donorId in the session
                session['user_email'] = email
                session['donor_id'] = donor_id  # Store donorId in session
                return redirect('/donor_dashboard')
            else:
                return "Donor ID not found", 400
        else:
            return "Donor not found in database", 404

    except Exception as e:
        return f"Invalid donor credentials: {str(e)}", 400




# ==================================
# 🔶 Charity Auth + Firestore Save
# ==================================

@app.route('/charity_signup', methods=['POST'])
def charity_signup():
    orgName = request.form['orgName']
    email = request.form['email']
    password = request.form['password']
    phone = request.form['phone']
    reg_file = request.files['registrationDocs']

    try:
        # Save uploaded file
        filename = f"{datetime.now().timestamp()}_{reg_file.filename}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        reg_file.save(filepath)
        reg_file_url = f"/{filepath}"

        # Firebase Auth
        user = auth.create_user_with_email_and_password(email, password)
        charityId = user['localId']

        # ✅ Save to Firestore
        db.collection("charities").document(charityId).set({
            "charityId": charityId,
            "orgName": orgName,
            "email": email,
            "phone": phone,
            "registrationDocs": reg_file_url,
            "status": "Pending",
            "createdAt": datetime.now()
        })

        return redirect('/charity_dashboard')

    except Exception as e:
        return f"Charity signup failed: {str(e)}"

@app.route('/charity_login', methods=['GET', 'POST'])
def charity_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        try:
            # Authenticate using Firebase Authentication
            user = auth.sign_in_with_email_and_password(email, password)

            # Now check Firestore for charity approval status
            charity_ref = db.collection('charities').where('email', '==', email).limit(1).stream()
            charity_doc = next(charity_ref, None)

            if charity_doc:
                charity_data = charity_doc.to_dict()

                # Check if the charity status is approved
                if charity_data.get('status') == 'approved':
                    session['charity_email'] = email
                    return redirect('/charity_dashboard')
                else:
                    return redirect('/pending_approval')
            else:
                return "Charity data not found in Firestore."
        
        except Exception as e:
            print("Login Error:", e)
            return "Invalid charity credentials or not registered."

    # GET request - show login form
    return render_template('auth_charity.html')




# ===============================
# 🔴 Admin Auth (Manual Only)
# ===============================

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

@app.route('/admin_login', methods=['POST'])
def admin_login():
    username = request.form['username']
    password = request.form['password']

    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        return redirect("/admin_dashboard")
    return "Invalid admin credentials"




# =============================
# Run App
# =============================

#***************************************************************************************************************************
@app.route('/donor_dashboard')
def donor_dashboard():
    return render_template('donor_dashboard.html')

@app.route('/explore_verified_charities', methods=['GET'])
def explore_verified_charities():
    cause_filter = request.args.get('cause', '').lower()
    location_filter = request.args.get('location', '').lower()

    charities_ref = db.collection('charities').where('status', '==', 'approved')
    docs = charities_ref.stream()

    charities = []
    for doc in docs:
        data = doc.to_dict()
        data['charityId'] = doc.id

        # Optional filters (if you're storing these fields in your schema)
        if cause_filter and cause_filter not in data.get('category', '').lower():
            continue
        if location_filter and location_filter not in data.get('location', '').lower():
            continue

        charities.append(data)

    return render_template('explore_verified_charities.html', charities=charities)

@app.route('/donate_now')
def donate_now():
    campaigns_ref = db.collection('campaigns')
    active_campaigns = campaigns_ref.where('active', '==', True).stream()

    campaign_list = []
    for doc in active_campaigns:
        data = doc.to_dict()
        data['campaignId'] = doc.id
        campaign_list.append(data)

    return render_template('donate_now.html', campaigns=campaign_list)

# Route to show full campaign details
@app.route('/campaign/<campaign_id>')
def campaign_details(campaign_id):
    campaign_ref = db.collection('campaigns').document(campaign_id)
    campaign_doc = campaign_ref.get()

    if not campaign_doc.exists:
        return "Campaign not found", 404

    campaign = campaign_doc.to_dict()
    campaign['campaignId'] = campaign_id

    # Calculate progress
    funds = campaign.get('fundsRaised', 0)
    target = campaign.get('targetAmountETH', 1)
    progress = min(int((funds / target) * 100), 100)

    return render_template('all_details_campaign.html', campaign=campaign, progress=progress)

@app.route('/view_donation_history')
def view_donation_history():
    # Get the email from the session (assumed to be stored as user_email)
    user_email = session.get('user_email')
    if not user_email:
        return redirect(url_for('donor_login'))

    # Fetch the donation records from Firestore for the logged-in user
    donations_ref = db.collection('donors')
    donations_query = donations_ref.where('email', '==', user_email).stream()

    donations_list = []
    for doc in donations_query:
        donation = doc.to_dict()
        donation['donationId'] = doc.id  # Add the document ID for the transaction
        donations_list.append(donation)

    # Render the 'view_donation_history.html' template with the donation data
    return render_template('view_donation_history.html', donations=donations_list)



@app.route('/download_receipt/<donation_id>')
def download_receipt(donation_id):
    # Get donor_id from session
    donor_id = session.get('donor_id')
    if not donor_id:
        return redirect(url_for('donor_login'))

    # Search for the donation in the donors collection by donation_id and donor_id
    donation_query = db.collection('donors')\
        .where('donorId', '==', donor_id)\
        .where('donation_id', '==', donation_id)\
        .limit(1).get()

    if not donation_query:
        return "Donation not found", 404

    donation = donation_query[0].to_dict()

    # Optionally fetch additional donor info from donors_login (if needed)
    donor_info_query = db.collection('donors_login')\
        .where('donorId', '==', donor_id)\
        .limit(1).get()

    if donor_info_query:
        donor_profile = donor_info_query[0].to_dict()
        donor_name = donor_profile.get('name', 'Anonymous')
        donor_email = donor_profile.get('email', '')
    else:
        donor_name = donation.get('name', 'Anonymous')  # fallback
        donor_email = donation.get('email', '')

    # Create PDF receipt
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.cell(200, 10, txt=f"Donation Receipt", ln=True)
    pdf.cell(200, 10, txt=f"Receipt ID: {donation_id}", ln=True)
    pdf.cell(200, 10, txt=f"Donor Name: {donor_name}", ln=True)
    pdf.cell(200, 10, txt=f"Email: {donor_email}", ln=True)
    pdf.cell(200, 10, txt=f"Amount: ₹{donation.get('amount', 0)}", ln=True)
    pdf.cell(200, 10, txt=f"Campaign ID: {donation.get('campaignId')}", ln=True)
    pdf.cell(200, 10, txt=f"Status: {donation.get('status', 'N/A')}", ln=True)
    pdf.cell(200, 10, txt=f"Date: {donation.get('createdAt').strftime('%Y-%m-%d %H:%M:%S') if donation.get('createdAt') else 'N/A'}", ln=True)

    # Generate PDF into BytesIO
    pdf_output = BytesIO()
    pdf.output(pdf_output, 'F')
    pdf_output.seek(0)

    return send_file(
        pdf_output,
        as_attachment=True,
        download_name=f"receipt_{donation_id}.pdf",
        mimetype='application/pdf'
    )

@app.route('/view_performance')
def view_performance():
    user_email = session.get('user_email')
    if not user_email:
        return redirect('/donor_login')

    # Get all donation records for this donor
    donors_ref = db.collection('donors')
    donation_docs = donors_ref.where('email', '==', user_email).where('amount', '>', 0).stream()

    campaign_ids = list({doc.to_dict()['campaignId'] for doc in donation_docs})

    campaigns = []
    for cid in campaign_ids:
        campaign_ref = db.collection('campaigns').where('campaignId', '==', cid).limit(1).stream()
        for doc in campaign_ref:
            data = doc.to_dict()
            campaigns.append(data)

    return render_template('charity_performance_redirect.html', campaigns=campaigns)

@app.route('/view_campaign_details/<campaign_id>')
def view_campaign_details(campaign_id):
    campaign_ref = db.collection('campaigns').where('campaignId', '==', campaign_id).limit(1).stream()
    campaign = None
    for doc in campaign_ref:
        campaign = doc.to_dict()
        break
    if not campaign:
        return "Campaign not found", 404
    return render_template('view_details_campaign.html', campaign=campaign)

@app.route('/charity_performance_redirect')
def charity_performance_redirect():
    return "Redirect to charity_history.html with org_id param"

@app.route('/write_review')
def write_review():
    user = session.get('user_email')
    if not user:
        return redirect('/donor_login')

    charities_ref = db.collection('charities').where('status', '==', 'approved')
    charities = []
    for doc in charities_ref.stream():
        charity = doc.to_dict()
        charity['charityId'] = doc.id

        # ✅ Convert Firestore timestamp to string directly
        if 'createdAt' in charity:
            charity['createdAt'] = charity['createdAt'].strftime('%Y-%m-%d %H:%M:%S')

        charities.append(charity)

    return render_template('write_a_review.html', charities=charities)

@app.route('/submit_review', methods=['POST'])
def submit_review():
    data = request.get_json()
    charity_id = data['charityId']
    review_text = data['review']
    user_email = session['user_email']
    timestamp = datetime.now()

    review_id = str(uuid.uuid4())
    review_data = {
        'reviewId': review_id,
        'charityId': charity_id,
        'review': review_text,
        'reviewedBy': user_email,
        'createdAt': timestamp
    }

    db.collection('charity_review').document(review_id).set(review_data)
    return jsonify({'message': 'Review submitted successfully!'}), 200

@app.route('/charity_details/<org_id>')
def charity_details(org_id):
    charity_ref = db.collection('charities').document(org_id)
    charity_doc = charity_ref.get()

    if not charity_doc.exists:
        return "Charity not found", 404

    charity = charity_doc.to_dict()
    charity['charityId'] = org_id

    campaign_docs = db.collection('campaigns').where('charityId', '==', org_id).stream()

    ongoing_campaigns = []
    past_campaigns = []

    now = datetime.now()

    for doc in campaign_docs:
        data = doc.to_dict()
        data['id'] = doc.id

        end_date_raw = data.get('endDate')

        if end_date_raw:
            try:
                if hasattr(end_date_raw, 'to_datetime'):
                    # It's a Firestore Timestamp
                    end_datetime = end_date_raw.to_datetime().replace(tzinfo=None)
                elif isinstance(end_date_raw, str):
                    # Parse ISO string to datetime
                    end_datetime = datetime.fromisoformat(end_date_raw)
                else:
                    # Unknown format, skip
                    continue

                data['endDate'] = end_datetime

                if end_datetime > now:
                    ongoing_campaigns.append(data)
                else:
                    past_campaigns.append(data)
            except Exception as e:
                print(f"Skipping campaign {doc.id} due to date error: {e}")
                continue

    return render_template('charity_details.html',
                           charity=charity,
                           ongoing_campaigns=ongoing_campaigns,
                           past_campaigns=past_campaigns)

@app.route('/donate_to_campaign/<campaign_id>', methods=['POST', 'GET'])
def donate_to_campaign(campaign_id):
    try:
        # Get the donation amount from the form
        amount = float(request.form.get('amount'))
        if amount <= 0:
            return "Invalid donation amount", 400
    except (TypeError, ValueError):
        return "Invalid donation amount", 400

    # Ensure user is logged in (session should have user details)
    user = session.get('user_email')  # Assuming 'user_email' stores the email or full user info

    if not user:
        return redirect(url_for('donor_login'))  # Redirect to login if user is not logged in

    # If the user info is stored as a dictionary, access necessary fields
    donor_id = user.get('localId') if isinstance(user, dict) else None
    email = user if isinstance(user, str) else user.get('email', '')  # If it's a string, it's the email
    name = user.get('name', 'Anonymous') if isinstance(user, dict) else 'Anonymous'
    phone = user.get('phone', '') if isinstance(user, dict) else ''

    # Fetch campaign document from Firestore
    campaign_ref = db.collection('campaigns').document(campaign_id)
    campaign_doc = campaign_ref.get()

    if not campaign_doc.exists:
        return "Campaign not found", 404  # Return error if campaign not found

    # Get campaign data
    campaign_data = campaign_doc.to_dict()
    current_funds = campaign_data.get('fundsRaised', 0)
    new_total = current_funds + amount

    # Update the campaign's 'fundsRaised' field in Firestore
    campaign_ref.update({'fundsRaised': new_total})

    # Add donation record to 'donors' collection in Firestore
    donor_info = {
        'donorId': donor_id,
        'email': email,
        'name': name,
        'phone': phone,
        'amount': amount,
        'campaignId': campaign_id,
        'status': "Successful",
        'createdAt': datetime.utcnow()
    }

    db.collection('donors').add(donor_info)

    # Redirect back to the charity details page with the campaign's charityId
    return redirect(url_for('charity_details', org_id=campaign_data['charityId']))
#***************************************************************************************************************************


#***************************************************************************************************************************
#charity dashboard

@app.route('/charity_dashboard')
def charity_dashboard():
    email = session.get('charity_email')
    if not email:
        return redirect(url_for('charity_login'))

    # Fetch charity info from Firestore using the session email
    charity_ref = db.collection('charities').where('email', '==', email).limit(1).stream()
    charity_doc = next(charity_ref, None)

    if charity_doc:
        charity_data = charity_doc.to_dict()

        # Check if the charity is approved
        if charity_data.get('status') == 'approved':
            return render_template('charity_dashboard.html', charity=charity_data)
        else:
            return redirect(url_for('pending_approval'))
    else:
        return "Charity data not found."

@app.route('/pending_approval')
def pending_approval():
    return "<h2>Your charity account is pending approval. Please wait for admin verification.</h2>"

@app.route('/create_campaign', methods=['GET', 'POST'])
def create_campaign():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        target_amount_eth = float(request.form['target_amount'])
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        category = request.form['category']

        charity_email = session.get('charity_email')
        if not charity_email:
            return redirect(url_for('charity_login'))

        # Retrieve charity data from Firestore
        charity_ref = db.collection('charities').where('email', '==', charity_email).limit(1).stream()
        charity_doc = next(charity_ref, None)
        if not charity_doc:
            return "Charity data not found."

        charity_data = charity_doc.to_dict()
        charity_id = charity_doc.id

        # Generate a unique campaign ID using uuid or timestamp
        campaign_id = str(uuid.uuid4())

        # Store campaign data in Firestore
        campaign_data = {
            'campaignId': campaign_id,
            'charityId': charity_id,
            'title': title,
            'description': description,
            'targetAmountETH': target_amount_eth,
            'startDate': start_date,
            'endDate': end_date,
            'category': category,
            'fundsRaised': 0,
            'active': True,
            'createdAt': datetime.utcnow()
        }

        db.collection('campaigns').document(campaign_id).set(campaign_data)

        return redirect(url_for('charity_dashboard'))

    return render_template('create_campaign.html')

@app.route('/view_my_campaigns')
def view_my_campaigns():
    # Check if the charity is logged in
    if 'charity_email' not in session:
        return redirect('/charity_login')

    charity_email = session['charity_email']
    charity_ref = db.collection('charities').where('email', '==', charity_email).limit(1).stream()
    charity_doc = next(charity_ref, None)
    
    if not charity_doc:
        return "Charity not found in Firestore."

    charity_data = charity_doc.to_dict()
    charity_id = charity_data.get('charityId')

    # Fetch all campaigns created by the charity
    campaigns_ref = db.collection('campaigns').where('charityId', '==', charity_id).stream()
    campaigns = []

    for campaign in campaigns_ref:
        campaign_data = campaign.to_dict()
        campaigns.append(campaign_data)

    return render_template('view_my_campaigns.html', campaigns=campaigns)

@app.route('/campaign_donations/<campaign_id>')
def campaign_donations(campaign_id):
    # Fetch donations related to the campaign
    donations_ref = db.collection('donations').where('campaignId', '==', campaign_id).stream()
    donations = []

    for donation in donations_ref:
        donation_data = donation.to_dict()
        donations.append(donation_data)

    return render_template('campaign_donations.html', donations=donations, campaign_id=campaign_id)

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif'}

# Ensure upload directory exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload_documents/<campaign_id>', methods=['GET', 'POST'])
def upload_documents(campaign_id):
    if request.method == 'POST':
        if 'proof_file' not in request.files:
            return "No file part in the request."

        proof_file = request.files['proof_file']
        if proof_file.filename == '':
            return "No file selected."

        if proof_file and allowed_file(proof_file.filename):
            filename = secure_filename(proof_file.filename)
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            proof_file.save(file_path)

            # Construct file URL
            file_url = url_for('static', filename='uploads/' + filename, _external=True)

            # Update Firestore campaign with proof document
            campaign_ref = db.collection('campaigns').document(campaign_id)
            campaign_ref.update({
                'proofOfUse': file_url,
                'status': 'Completed'
            })

            return redirect(url_for('view_my_campaigns'))
        else:
            return "File type not allowed. Please upload a valid image or PDF file."

    return render_template('upload_documents.html', campaign_id=campaign_id)

@app.route('/withdraw_fund')
def withdraw_fund():
    if 'charity_email' not in session:
        return redirect('/charity_login')

    charity_email = session['charity_email']
    charity_ref = db.collection('charities').where('email', '==', charity_email).limit(1).stream()
    charity_doc = next(charity_ref, None)
    if not charity_doc:
        return "Charity not found", 404
    charity_data = charity_doc.to_dict()
    charity_id = charity_data.get('charityId')

    campaigns_ref = db.collection('campaigns').where('charityId', '==', charity_id).stream()
    campaigns = []
    for doc in campaigns_ref:
        data = doc.to_dict()
        data['campaignId'] = doc.id
        campaigns.append(data)

    return render_template('withdraw_fund.html', campaigns=campaigns, now_utc=datetime.utcnow())

@app.route('/process_withdraw', methods=['POST'])
def process_withdraw():
    if 'charity_email' not in session:
        return redirect('/charity_login')

    charity_email = session['charity_email']

    # Fetch charityId using email
    charity_ref = db.collection('charities').where('email', '==', charity_email).limit(1).stream()
    charity_doc = next(charity_ref, None)
    if not charity_doc:
        return "Charity not found", 404
    charity_data = charity_doc.to_dict()
    charity_id = charity_data.get('charityId')

    # Get form data
    campaign_id = request.form['campaignId']
    account_holder = request.form['account_holder']
    account_number = request.form['account_number']
    description = request.form['description']
    usage_domain = request.form['usage_domain']

    campaign_ref = db.collection('campaigns').document(campaign_id)
    campaign_doc = campaign_ref.get()

    if not campaign_doc.exists:
        return "Campaign not found", 404

    campaign_data = campaign_doc.to_dict()

    if campaign_data['status'] not in ['Verified', 'Completed']:
        return "Withdraw not allowed for this campaign", 403

    withdraw_time = datetime.utcnow()

    campaign_ref.update({
        'withdraw_status': 'completed',
        'raisedAmount': 0,
        'withdraw_date': withdraw_time  # ✅ Add withdraw date
    })

    withdrawal_data = {
        'charityId': charity_id,
        'charityEmail': charity_email,
        'campaignId': campaign_id,
        'campaignTitle': campaign_data.get('title', ''),
        'account_holder': account_holder,
        'account_number': account_number,
        'description': description,
        'usage_domain': usage_domain,
        'withdraw_date': withdraw_time,
        'amount_withdrawn': campaign_data.get('raisedAmount', 0),
        'campaign_status': campaign_data.get('status', '')
    }

    db.collection('charity_withdrawal').add(withdrawal_data)

    return redirect('/withdraw_fund')

# Upload Fund Usage Proof
@app.route('/upload_withdraw_proof', methods=['POST'])
def upload_withdraw_proof():
    campaign_id = request.form.get('campaignId')
    file = request.files.get('proof_document')

    if not campaign_id or not file or file.filename == '':
        return "Missing campaign ID or file", 400

    # Securely save uploaded file
    filename = secure_filename(file.filename)
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(file_path)

    # Create public file URL
    file_url = url_for('static', filename=f'uploads/{filename}', _external=True)

    # Get campaign document from Firestore
    campaign_ref = db.collection('campaigns').document(campaign_id)
    campaign_doc = campaign_ref.get()

    if not campaign_doc.exists:
        return "Campaign not found", 404

    campaign_data = campaign_doc.to_dict()
    withdraw_date = campaign_data.get('withdraw_date')

    '''if not withdraw_date:
        return "Withdraw date not found", 400

    # Ensure withdraw_date is timezone-aware (Firestore timestamps are)
    if withdraw_date.tzinfo is None:
        withdraw_date = withdraw_date.replace(tzinfo=pytz.utc)

    now = datetime.utcnow().replace(tzinfo=pytz.utc)
    deadline = withdraw_date + timedelta(days=30)

    if now > deadline:
        return "Upload deadline expired", 403'''

    # Update campaign document with proof file URL
    campaign_ref.update({
        'withdraw_fund_usage_proof': file_url
    })

    return redirect('/withdraw_fund')

@app.route('/performance_report')
def performance_report():
    return "<h2>Campaign Performance Report Page (To Be Implemented)</h2>"

@app.route('/manage_charity_profile', methods=['GET', 'POST'])
def manage_charity_profile():
    charity_email = session.get('charity_email')
    if not charity_email:
        return redirect('/charity_login')

    charities_ref = db.collection('charities').where('email', '==', charity_email).stream()
    charity_doc = next(charities_ref, None)

    if not charity_doc:
        return "Charity not found", 404

    doc_id = charity_doc.id
    charity_data = charity_doc.to_dict()

    if request.method == 'POST':
        updated_orgName = request.form.get('orgName')
        updated_phone = request.form.get('phone')

        updated_data = {
            'orgName': updated_orgName,
            'phone': updated_phone
        }

        # Handle registration document upload
        if 'registrationDocs' in request.files:
            file = request.files['registrationDocs']
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                filepath = os.path.join('static/uploads', filename)
                file.save(filepath)
                updated_data['registrationDocs'] = '/' + filepath.replace('\\', '/')

        db.collection('charities').document(doc_id).update(updated_data)
        flash('Profile updated successfully!', 'success')
        return redirect('/charity_dashboard')

    return render_template('manage_charity_profile.html', charity=charity_data)

@app.route('/view_donations/<campaign_id>')
def view_donations(campaign_id):
    return f"Donations for campaign ID: {campaign_id} (Coming Soon)"
#***************************************************************************************************************************



#***************************************************************************************************************************
#admin dashboard

@app.route('/admin_dashboard')
def admin_dashboard():
    return render_template('admin_dashboard.html')

@app.route('/admin_campaigns')
def admin_campaigns():
    campaigns_ref = db.collection('campaigns').stream()
    campaigns = [c.to_dict() for c in campaigns_ref]
    return render_template('admin_campaigns.html', campaigns=campaigns)

@app.route('/flag_campaign', methods=['POST'])
def flag_campaign():
    campaign_id = request.form.get('campaign_id')
    action = request.form.get('action')

    if not campaign_id or not action:
        return "Missing parameters", 400

    campaign_ref = db.collection('campaigns').document(campaign_id)

    if action == 'fraudulent':
        campaign_ref.update({'status': 'Flagged'})
    elif action == 'verified':
        campaign_ref.update({'status': 'Verified'})

    return redirect(url_for('admin_campaigns'))

@app.route('/global_donation_ledger')
def global_donation_ledger():
    donors_ref = db.collection('donors').stream()
    donation_records = []

    for doc in donors_ref:
        data = doc.to_dict()

        # Only include records that contain donation-related fields
        if all(key in data for key in ['amount', 'campaignId', 'createdAt', 'donorId']):
            donation_records.append({
                'donor_address': data.get('donorId', ''),
                'campaign': data.get('campaignId', ''),
                'charity': '',  # You can fill this in if you have a way to look up charity from campaignId
                'amount': data.get('amount', 0),
                'timestamp': data.get('createdAt').strftime('%Y-%m-%d %H:%M:%S') if isinstance(data.get('createdAt'), datetime) else '',
                'tx_hash': data.get('tx_hash', 'N/A')  # Optional, if stored
            })

    return render_template('admin_donation_ledger.html', donations=donation_records)

@app.route('/admin_disputes')
def admin_disputes():
    # Fetch active campaigns
    campaigns_ref = db.collection('campaigns').where('active', '==', True)
    campaigns_docs = campaigns_ref.stream()

    campaigns = []
    for doc in campaigns_docs:
        data = doc.to_dict()
        data['campaignId'] = doc.id
        campaigns.append(data)

    return render_template('admin_disputes.html', campaigns=campaigns)

@app.route('/handle_dispute_action', methods=['POST'])
def handle_dispute_action():
    campaign_id = request.form.get('campaignId')
    charity_id = request.form.get('charityId')
    action = request.form.get('action')

    if not campaign_id or not action:
        flash('Missing campaign ID or action.')
        return redirect('/admin_disputes')

    campaign_ref = db.collection('campaigns').document(campaign_id)
    campaign_doc = campaign_ref.get()

    if not campaign_doc.exists:
        flash('Campaign not found.')
        return redirect('/admin_disputes')

    # Apply the selected action
    if action == 'freeze':
        campaign_ref.update({'status': 'Freezed'})
        flash('Campaign has been frozen.')

    elif action == 'ban':
        charity_ref = db.collection('charities').document(charity_id)
        charity_ref.update({'status': 'banned'})
        flash('Charity has been banned.')

    elif action == 'refund':
        campaign_ref.update({'fundsRaised': 0})
        flash('Funds have been forcefully refunded.')

    else:
        flash('Invalid action.')
        return redirect('/admin_disputes')

    # Log the dispute
    db.collection('disputes').add({
        'campaignId': campaign_id,
        'charityId': charity_id,
        'action': action,
        'timestamp': datetime.now(pytz.utc)
    })

    return redirect('/admin_disputes')

@app.route('/admin_system_analytics')
def admin_system_analytics():
    # Count total charities
    charities_ref = db.collection('charities').stream()
    total_charities = sum(1 for _ in charities_ref)

    # Count total donors
    donors_ref = db.collection('donors_login').stream()
    total_donors = sum(1 for _ in donors_ref)

    # Count total reviews
    reviews_ref = db.collection('charity_review').stream()
    total_reviews = sum(1 for _ in reviews_ref)

    # Count total donation transactions
    transactions_ref = db.collection('donors').stream()
    total_transactions = sum(1 for _ in transactions_ref)

    # Count campaign statuses
    campaigns = db.collection('campaigns').stream()
    status_counts = {
        'Verified': 0,
        'Completed': 0,
        'active': 0,
        'Fraudulent': 0
    }

    for doc in campaigns:
        data = doc.to_dict()
        status = data.get('status')
        if status in status_counts:
            status_counts[status] += 1

    return render_template(
        'admin_system_analytics.html',
        total_charities=total_charities,
        total_donors=total_donors,
        total_reviews=total_reviews,
        total_transactions=total_transactions,
        status_counts=status_counts
    )

@app.route('/logout')
def logout():
    #session.clear()
    return redirect('/')


@app.route('/pending_charities')
def pending_charities():
    charities_ref = db.collection('charities')
    pending_charities = charities_ref.where("status", "==", "Pending").stream()

    charities = []
    for charity in pending_charities:
        data = charity.to_dict()
        data['id'] = charity.id  # Firestore doc ID
        # Convert createdAt timestamp to datetime
        if 'createdAt' in data:
            data['createdAt'] = data['createdAt'].replace(tzinfo=None)  # remove timezone for clean display
        charities.append(data)

    return render_template('pending_charities.html', charities=charities)

# Handle approval
@app.route('/approve_charity/<charity_id>', methods=['POST'])
def approve_charity(charity_id):
    db.collection('charities').document(charity_id).update({"status": "approved"})
    return redirect(url_for('pending_charities'))

# Handle rejection
@app.route('/reject_charity/<charity_id>', methods=['POST'])
def reject_charity(charity_id):
    db.collection('charities').document(charity_id).update({"status": "rejected"})
    return redirect(url_for('pending_charities'))

#***************************************************************************************************************************






if __name__ == "__main__":
    app.run(debug=True)