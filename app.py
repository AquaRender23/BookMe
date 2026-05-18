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
resources_collection = db["resources"]
users_collection = db["users"]

users_collection.create_index(
    "email",
    unique=True
)

#Initialize resources
def initialize_resources():
    existing_resources = resources_collection.count_documents({})

    if existing_resources > 0:
        return 
    
    resources_data = []

    labs = [
        ("01","Chemistry Lab", 25),
        ("02","Physics Lab", 25),
        ("03", "Computer Lab", 60),
        ("04", "Electronics Lab", 30)
    ]

    sports = [
    ("05", "Football Ground", 22),
    ("06", "Basketball Court", 10),
    ("07", "Badminton Court", 4),
    ("08", "Tennis Court", 4)
    ]

    rooms = [
    ("09", "Seminar Hall", 100),
    ("10", "Meeting Room", 20)
    ]

    for i in range(1, 11):
        resources_data.append({
            "resource_id": f"P{i}",
            "resource_name": f"Parking Slot {i}",
            "category": "parking",
            "capacity": 1,
            "description": "Vehicle parking slot",
            "status": "available"
        })

    for resource_id, resource_name, capacity in labs:
        resources_data.append({
            "resource_id": resource_id,
            "resource_name": resource_name,
            "category": "lab",
            "capacity": capacity,
            "description": "Lab resource",
            "status": "available"
        })

    for resource_id, resource_name, capacity in sports:
        resources_data.append({
            "resource_id": resource_id,
            "resource_name": resource_name,
            "category": "sport",
            "capacity": capacity,
            "description": "Sports resource",
            "status": "available"
        })

    for resource_id, resource_name, capacity in rooms:
        resources_data.append({
            "resource_id": resource_id,
            "resource_name": resource_name,
            "category": "room",
            "capacity": capacity,
            "description": "Room resource",
            "status": "available"
        })

    resources_collection.insert_many(resources_data)
    
initialize_resources()

#Update booking status 
def update_booking_status():
    active_bookings = bookings_collection.find({
    "booking_status": "confirmed"
})
    current_time = datetime.now()

    for booking in active_bookings:
        booking_end = datetime.strptime(
            booking["booking_date"] + " " + booking["end_time"], "%Y-%m-%d %H:%M"
        )
        if booking_end < current_time:
            bookings_collection.update_one(
                {
                    "_id": booking["_id"]
                },
                {
                    "$set":{
                        "booking_status": "no_show"
                    }
                }
            )

            users_collection.update_one(
                {
                    "email": booking["user_email"]
                },
                {
                    "$inc": {
                        "ghost_count": 1,
                        "reputation_score": -5
                    }
                }
            )
    

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
    
    labs_data = resources_collection.find({
        "category" : "lab"
    })
    
    return render_template("labs.html", labs=labs_data)

#Sports
@app.route('/sports', methods=['GET','POST'])
def sports():
    if "user_email" not in session:
        return redirect(url_for("login"))
    
    sports_data = resources_collection.find({
       "category" : "sport" 
    })
    
    return render_template("sports.html", sports=sports_data)

#Rooms
@app.route('/rooms', methods=['GET','POST'])
def rooms():
    if "user_email" not in session:
        return redirect(url_for("login"))
    
    rooms_data = resources_collection.find({
        "category" : "room"
    })
    return render_template("rooms.html", rooms=rooms_data)

#Parking
@app.route('/parking', methods=['GET','POST'])
def parking():
    if "user_email" not in session:
        return redirect(url_for("login"))
    
    parking_data = resources_collection.find({
        "category" : "parking"
    })
    
    return render_template("parking.html", parking=parking_data)

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

    current_user = users_collection.find_one({
        "email" : session["user_email"]
    })
    if current_user["reputation_score"] < 30:
        return "Cannot book due to low reputation score "

    booking_day = datetime.strptime(
        booking_date, "%Y-%m-%d"
    ).date()
    today = datetime.now().date()

    if booking_day < today:
        return "Cannot book past days"

    resource = resources_collection.find_one({
        "resource_id" : resource_id
    })
    if resource['status'] != "available":
        return "Booking unavailable"
    
    existing_bookings = bookings_collection.find({
        "resource_id" : resource_id,
        "booking_date" : booking_date
    }) 

    new_start = datetime.strptime(start_time, "%H:%M")
    new_end = datetime.strptime(end_time, "%H:%M")

    if new_end <= new_start:
        return "Invalid booking"

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
    
    if booking["booking_status"] == "cancelled":
        return "Booking already cancelled "
    
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

#Resources
@app.route('/resource/<resource_id>')
def resource(resource_id):
    if "user_email" not in session:
        return redirect(url_for("login"))
    
    resource_data=resources_collection.find_one({
        "resource_id" : resource_id
    })
    
    if resource_data == None:
        return "Resource Not Found" 
    
    return render_template("resource.html", resource=resource_data)

#Availability
@app.route('/availability/<resource_id>')
def availability(resource_id):
    if "user_email" not in session:
        return redirect(url_for("login"))
    
    booking_date = request.args.get("booking_date")

    if not booking_date:
        return "Booking date required"
    
    existing_bookings = bookings_collection.find({
        "resource_id" : resource_id,
        "booking_date" : booking_date
    })

    booking_slots = []

    for booking in existing_bookings:
        booking_slots.append({
            "start_time": booking["start_time"],
            "end_time": booking["end_time"]
        })

    return{
        "resource_id": resource_id,
        "booking_date": booking_date,
        "booking_slots": booking_slots
    }
    

if __name__ == '__main__':
    app.run(debug=True)