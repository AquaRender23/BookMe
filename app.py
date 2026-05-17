from flask import Flask, render_template, request, redirect, url_for, session
from pymongo import MongoClient
from dotenv import load_dotenv
import os
from flask_bcrypt import Bcrypt
from authlib.integrations.flask_client import OAuth
from datetime import datetime
from bson.objectid import ObjectId

load_dotenv()

app = Flask(__name__)
bcrypt = Bcrypt(app)
oauth = OAuth(app)

app.secret_key = os.getenv("SECRET_KEY")
mongo_uri = os.getenv("MONGO_URI")

client = MongoClient(mongo_uri)
db = client["BookMe"]
bookings_collection = db["bookings"]

sample_booking = {
    "user_email": "test@gmail.com",
    "resource_id": "chem_lab_01",
    "booking_date": "2026-05-20",
    "start_time": "10:00",
    "end_time": "11:00",
    "booking_status": "confirmed",
    "created_at": datetime.now()
}
bookings_collection.insert_one(sample_booking)


#Google OAuth
google = oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

#Register
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'GET':
        return render_template("register.html")

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password= request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not name or not email or not password or not confirm_password:
            return "All fields are required"
        
        if password != confirm_password:
            return "Passwords do not match"

        users_collection = db["users"]
        existing_user = users_collection.find_one({
            "email":email
        })
        if existing_user:
            return "User already exists"
        
        hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")

        user_data = {
            "name": name,
            "email": email,
            "password": hashed_password,
            "reputation_score": 100,
            "ghost_count": 0,
            "role": "student"
        }
        users_collection.insert_one(user_data)
        return redirect(url_for('login'))
    
    return redirect(url_for('register'))
    
#Login  
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'GET':
        return render_template("login.html")
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            return "All fields are required"
        
        users_collection = db['users']
        user = users_collection.find_one({
            "email": email
        })
        if not user:
            return "User not found"
        
        password_match = bcrypt.check_password_hash(user["password"],password)
        if not password_match:
            return "Password not correct"
        
        session["user_email"] = user["email"]
        session["user_name"] = user["name"]

        return redirect(url_for('home'))
    
    return redirect(url_for('login'))
    
#Google Login
@app.route('/google-login')
def google_login():

    return google.authorize_redirect(
        url_for('google_callback', _external=True)
    )

@app.route('/google/callback')
def google_callback():

    token = google.authorize_access_token()

    user_info = token['userinfo']

    email = user_info['email']
    name = user_info['name']

    users_collection = db["users"]

    existing_user = users_collection.find_one({
        "email": email
    })

    # Create account if first login
    if not existing_user:

        user_data = {
            "name": name,
            "email": email,
            "password": None,
            "reputation_score": 100,
            "ghost_count": 0,
            "role": "student"
        }

        users_collection.insert_one(user_data)

    # Create session
    session["user_email"] = email
    session["user_name"] = name

    return redirect(url_for('home'))

#Homepage
@app.route('/', methods=['GET'])
def home():
    if "user_email" not in session:
        return redirect (url_for("login"))
    
    return render_template("home.html",user_name=session["user_name"])

#Logout
@app.route('/logout', methods=['GET','POST'])
def logout():
    session.pop("user_name", None)
    session.pop("user_email",None)

    return redirect (url_for("login"))

#Labs
@app.route('/labs',methods=['GET','POST'])
def labs():
    if "user_email" not in session:
        return redirect(url_for("login"))
    
    return render_template("labs.html")

#Sports
@app.route('/sports', methods=['GET','POST'])
def sports():
    if "user_email" not in session:
        return redirect(url_for("login"))
    
    return render_template("sports.html")

#Rooms
@app.route('/rooms', methods=['GET','POST'])
def rooms():
    if "user_email" not in session:
        return redirect(url_for("login"))
    
    return render_template("rooms.html")

#Parking
@app.route('/parking', methods=['GET','POST'])
def parking():
    if "user_email" not in session:
        return redirect(url_for("login"))
    
    return render_template("parking.html")

#Book resources
@app.route('/book_resource', methods=['POST'])
def book_resource():
    if "user_email" not in session:
        return redirect(url_for("login"))
    
    resource_id = request.form.get("resource_id")
    booking_date = request.form.get("booking_date")
    start_time = request.form.get("start_time")
    end_time = request.form.get("end_time")

    user_email = session["user_email"]

    if not resource_id or not booking_date or not start_time or not end_time:
        return "All fields are required"
    
    existing_bookings = bookings_collection.find({
        "resource_id" : resource_id,
        "booking_date" : booking_date
    }) 

    new_start = datetime.strptime(start_time, "%H:%M")
    new_end = datetime.strptime(end_time, "%H:%M")

    for booking in existing_bookings:
        existing_start = datetime.strptime(
            booking["start_time"],
            "%H:%M"
        )
        existing_end = datetime.strptime(
            booking["end_time"],
            "%H:%M"
        )

        if new_start < existing_end and new_end > existing_start:
            return "Slot already booked"
        
        booking_data = {
        "user_email": user_email,
        "resource_id": resource_id,
        "booking_date": booking_date,
        "start_time": start_time,
        "end_time": end_time,
        "booking_status": "confirmed",
        "created_at": datetime.now()
    }
        
    bookings_collection.insert_one(booking_data)
    return "Booking successful"

#Cancel bookings
@app.route('/cancel-booking/<booking_id>')
def cancel_booking(booking_id):
    if "user_email" not in session:
        return redirect(url_for("login"))
    
    booking = bookings_collection.find_one({
        "_id" : ObjectId(booking_id)
    })

    if not booking:
        return "Booking Not Found"
    
    if booking['user_email'] != session['user_email']:
        return "Unauthorized access"
    
    bookings_collection.update_one({
        "_id" : ObjectId(booking_id)
    },
    {
        "$set":{
            "booking_status": "cancelled"
        }
    })
    users_collection.update_one({
        "email" : session["user_email"]
    },
    {
        "$inc":{
            "ghost_count": 1,
            "reputation_score": -5
        }
    })
    return "Booking cancelled successfully"

#Booking history
@app.route('/history')
def history():
    if "user_email" not in session:
        return redirect(url_for("login"))
    
    user_email = session["user_email"]

    user_bookings = bookings_collection.find({
        "user_email" : user_email
    })

    return render_template("history.html", bookings = user_bookings)
    


if __name__ == '__main__':
    app.run(debug=True)
