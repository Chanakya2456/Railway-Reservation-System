from flask import Flask, render_template, request, redirect, flash, url_for, session, make_response
from flask_session import Session
from datetime import datetime, timedelta
import random
import pdfkit
import mysql.connector

app = Flask(__name__)
app.config["CACHE_TYPE"] = "null"
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)
app.secret_key = "your_secret_key"  # Necessary for flash messages

path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)

# Database connection
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="chandu@123",
        database="train"
    )

@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.route("/")
def index():
    if (not session.get('user')):
        return redirect(url_for('login'))
    return redirect(url_for('home'))

@app.route("/login", methods=['GET', 'POST'])
def login():
    session.clear()
    if request.method == "POST":
        user = request.form['userId']
        password = request.form['password']

        connection = get_db_connection()
        cursor = connection.cursor()
        
        login_query = """
        SELECT Pwd
        FROM Login
        WHERE UserID = %s
        """

        cursor.execute(login_query, (user,))
        details = cursor.fetchall()
        if password==details[0][0]:
            session['user']=user
            return redirect(url_for('loading'))
        flash("Password Incorrect")
        return redirect(url_for('login'))
    return render_template('login.html')

@app.route("/register", methods=['GET', 'POST'])
def register():
    session.clear()
    if request.method == "POST":
        user = request.form['userId']
        password = request.form['password']
        mobile_no = request.form['mobileNumber']

        connection = get_db_connection()
        cursor = connection.cursor()

        register_query = """
        INSERT INTO Login (UserId, Pwd, Mobile_no)
        VALUES (%s, %s, %s)
        """

        cursor.execute(register_query, (user, password, mobile_no))
        connection.commit()
        flash(f"Registration successful")
        
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route("/logout")
def logout():
    session.clear()
    return render_template('login.html')

@app.route("/loading")
def loading():
    if (not session.get('user')):
        return redirect(url_for('login'))
    return render_template('loading.html')

@app.route("/home")
def home():
    if (not session.get('user')):
        return redirect(url_for('login'))
    flash(session['user'])
    return render_template('index.html', username=session['user'])

@app.route("/about")
def about():
    if (not session.get('user')):
        return redirect(url_for('login'))
    return render_template('about.html')

@app.route("/booktrain")
def booktrain():
    if (not session.get('user')):
        return redirect(url_for('login'))
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.execute("""SELECT station_name, min_order
    FROM (
    SELECT station_name, MIN(order_in_route) AS min_order
    FROM stations
    GROUP BY station_name) AS unique_stations
    ORDER BY min_order;
    """)
    stations = [row for row in cursor.fetchall()]
    min_date = datetime.now().date() + timedelta(days=1)
    max_date = min_date + timedelta(days=7)
    flash(max_date)
    connection.close()
    return render_template('booktrain.html', stations=stations, min_date=min_date, max_date=max_date)

@app.route("/bookings")
def bookings():
    if (not session.get('user')):
        return redirect(url_for('login'))
    connection = get_db_connection()
    cursor = connection.cursor()

    today = datetime.today().date()
    now = datetime.now().time()
    flash(now)

    current_bookings_query = """
    SELECT DISTINCT tr.train_number, tr.train_name, t.ticket_cluster, t.ticket_type, t.departure_date, t.arrival_date, t.departure_time, t.arrival_time, t.ticket_source, t.ticket_destination
    FROM MyTickets mt
    JOIN tickets t ON mt.ticket_ID = t.ticket_ID
    JOIN booking b ON b.ticket_ID = t.ticket_ID
    JOIN reservation r ON r.ticket_ID = t.ticket_ID
    JOIN trains tr ON tr.train_number = r.train_number
    JOIN passengers p ON p.adhaar_number = b.adhaar_number
    WHERE mt.UserId = %s AND (t.departure_date > %s OR (t.departure_date = %s AND t.departure_time > %s))
    ORDER BY t.departure_date ASC, t.departure_time ASC, t.ticket_cluster ASC
    """
    cursor.execute(current_bookings_query, (session['user'], today, today, now))
    current_cluster_details = cursor.fetchall()
    flash(current_cluster_details)

    past_bookings_query = """
    SELECT DISTINCT tr.train_number, tr.train_name, t.ticket_cluster, t.ticket_type, t.departure_date, t.arrival_date, t.departure_time, t.arrival_time, t.ticket_source, t.ticket_destination
    FROM MyTickets mt
    JOIN tickets t ON mt.ticket_ID = t.ticket_ID
    JOIN booking b ON b.ticket_ID = t.ticket_ID
    JOIN reservation r ON r.ticket_ID = t.ticket_ID
    JOIN trains tr ON tr.train_number = r.train_number
    JOIN passengers p ON p.adhaar_number = b.adhaar_number
    WHERE mt.UserId = %s AND (t.departure_date < %s OR (t.departure_date = %s AND t.departure_time <= %s))
    ORDER BY t.departure_date ASC, t.departure_time ASC, t.ticket_cluster ASC
    """
    cursor.execute(past_bookings_query, (session['user'], today, today, now))
    past_cluster_details = cursor.fetchall()
    flash(past_cluster_details)

    return render_template('bookings.html', current_tickets=current_cluster_details, past_tickets=past_cluster_details)

@app.route('/printTicket/ticket<filename>', methods=['POST'])
def printTicket(filename):
    if (not session.get('user')):
        return redirect(url_for('login'))
    
    cluster = request.form['ticket_cluster']
    
    connection = get_db_connection()
    cursor = connection.cursor()
    
    print_query = """
    SELECT DISTINCT tr.train_number, tr.train_name, t.ticket_cluster, t.ticket_type, t.departure_date, t.arrival_date, t.departure_time, t.arrival_time, t.ticket_source, t.ticket_destination, t.amount
    FROM MyTickets mt
    JOIN tickets t ON mt.ticket_ID = t.ticket_ID
    JOIN booking b ON b.ticket_ID = t.ticket_ID
    JOIN reservation r ON r.ticket_ID = t.ticket_ID
    JOIN trains tr ON tr.train_number = r.train_number
    JOIN passengers p ON p.adhaar_number = b.adhaar_number
    WHERE ticket_cluster = %s
    """
    cursor.execute(print_query, (cluster, ))
    ticket_details = cursor.fetchone()

    passenger_query = """
    SELECT p.passenger_name, p.age, p.sex, t.coach_no, t.berth_no, t.ticket_ID
    FROM tickets t
    JOIN booking b ON b.ticket_ID = t.ticket_ID
    JOIN passengers p ON p.adhaar_number = b.adhaar_number
    WHERE ticket_cluster = %s
    """
    cursor.execute(passenger_query, (cluster, ))
    passenger_details = cursor.fetchall()
    
    rendered = render_template('ticket.html', train_number=ticket_details[0], train_name=ticket_details[1], train_departure=ticket_details[6], train_arrival=ticket_details[7], source=ticket_details[8], destination=ticket_details[9], travel_date=ticket_details[4],
    arrival_date=ticket_details[5], ticket_type=ticket_details[3], amount=ticket_details[10], passengers=passenger_details)

    options = {
        'page-size': 'A3',
        'orientation': 'portrait',
        'margin-top': '0.5in',
        'margin-right': '0.5in',
        'margin-bottom': '0.5in',
        'margin-left': '0.5in',
        'encoding': "UTF-8",
        'custom-header': [
            ('Accept-Encoding', 'gzip')
        ],
        'no-outline': None
    }

    ticket = pdfkit.from_string(rendered,False, configuration=config, options=options)

    response = make_response(ticket)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=ticket{filename}.pdf'

    return response

@app.route("/trainlist", methods=['POST'])
def trainlist():
    if (not session.get('user')):
        return redirect(url_for('login'))
    session['source'] = request.form['source'][2:]
    session['destination'] = request.form['destination'][2:]
    src = request.form['source'][0:1]
    dst = request.form['destination'][0:1]
    travel_date = request.form['journey_date']
    session['travel_date'] = travel_date
    travel_day = datetime.strptime(travel_date, "%Y-%m-%d").strftime('%A')
    flash(f"{travel_date}{travel_day}")
    connection = get_db_connection()
    cursor = connection.cursor()
    if src<dst:
        query = """
        SELECT t.train_name, t.train_number, ta.available_ac_seats, ta.available_gen_seats, sd.departure_time, sa.arrival_time, t.price_per_ticket 
        FROM trains t
        JOIN stations sd on sd.station_name = %s
        JOIN stations sa on sa.station_name = %s
        JOIN stations sa_src ON t.src = sa_src.station_name
        JOIN stations sa_dest ON t.destination = sa_dest.station_name
        JOIN train_availability ta ON t.train_number = ta.train_number
        WHERE (sa_src.order_in_route <= (SELECT order_in_route FROM stations WHERE stations.station_name = %s) AND 
        sa_dest.order_in_route >= (SELECT order_in_route FROM stations WHERE stations.station_name = %s))
        AND ta.day_of_week = %s
        AND (ta.available_ac_seats > 0
        OR ta.available_gen_seats > 0)
        """
    else:
        query = """
        SELECT t.train_name, t.train_number, ta.available_ac_seats, ta.available_gen_seats, sa.departure_time, sd.arrival_time, t.price_per_ticket 
        FROM trains t
        JOIN stations sd on sd.station_name = %s
        JOIN stations sa on sa.station_name = %s
        JOIN stations sa_src ON t.src = sa_src.station_name
        JOIN stations sa_dest ON t.destination = sa_dest.station_name
        JOIN train_availability ta ON t.train_number = ta.train_number
        WHERE (sa_src.order_in_route > sa_dest.order_in_route AND 
        sa_src.order_in_route >= (SELECT order_in_route FROM stations WHERE stations.station_name = %s) AND sa_dest.order_in_route <= (SELECT order_in_route FROM stations WHERE stations.station_name = %s))
        AND ta.day_of_week = %s
        AND (ta.available_ac_seats > 0
        OR ta.available_gen_seats > 0)
        """
    cursor.execute(query, (session['source'], session['destination'], session['source'], session['destination'], travel_day))
    trains = cursor.fetchall()
    connection.close()
    flash(trains)
    session['train_departure']=trains[0][4]
    session['train_arrival']=trains[0][5]
    
    if session['train_departure']>session['train_arrival']:
        arrival_date = datetime.strptime(travel_date, "%Y-%m-%d") + timedelta(days=1)
        session['journey_time']=timedelta(hours=24)-(session['train_departure']-session['train_arrival'])
    else:
        arrival_date = datetime.strptime(travel_date, "%Y-%m-%d")
        session['journey_time']=session['train_arrival']-session['train_departure']
    
    arrival_date= arrival_date.strftime("%Y-%m-%d")
    session['arrival_date']=arrival_date

    return render_template('trainlist.html', trains=trains, travel_date=travel_date, arrival_date=arrival_date, source=session['source'], destination=session['destination'], journey_time=session['journey_time'])

@app.route("/passengers", methods=['POST'])
def passengers():
    if (not session.get('user')):
        return redirect(url_for('login'))
    session['train_number'] = request.form['train_number']
    session['train_name'] = request.form['train_name']
    session['ticket_type'] = request.form['ticket_type']
    session['amount'] = request.form['amount']
    if session['ticket_type']=="General":
        session['amount'] = int(session['amount'])/2
    flash(request.form)
    return render_template('passengers.html')

@app.route("/payment", methods=['POST'])
def payment():
    if (not session.get('user')):
        return redirect(url_for('login'))
    session['passenger_name'] = request.form.getlist('passenger_name')
    session['age'] = request.form.getlist('age')
    session['mobile_no'] = request.form.getlist('mobile_no')
    session['adhaar_number'] = request.form.getlist('adhaar_number')
    session['sex'] = request.form.getlist('sex')
    amount = 0
    for i in range(len(session['passenger_name'])):
        if(session['passenger_name'][i]):
            amount = amount + int(session['amount'])
    flash(request.form)
    return render_template('payment.html', amount=amount)

@app.route('/success', methods=['POST'])
def success():
    if (not session.get('user')):
        return redirect(url_for('login'))
    session['ticket_cluster'] = random.randint(1000, 9999)
    for i in range(len(session['passenger_name'])):
        flash(session['passenger_name'][i])
        if(session['passenger_name'][i]):
            try:
                ticket_id = random.randint(100000, 999999)
                flash(f"{ticket_id}")
                connection = get_db_connection()
                cursor = connection.cursor()

                # Insert passenger details
                passenger_query = """
                INSERT IGNORE INTO passengers (passenger_name, age, mobile_no, adhaar_number, sex)
                VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(passenger_query, (session['passenger_name'][i], session['age'][i], session['mobile_no'][i], session['adhaar_number'][i], session['sex'][i]))

                # Update available seats
                if session['ticket_type']=="AC":
                    update_seats_query = """
                    UPDATE train_availability 
                    SET available_ac_seats = available_ac_seats - 1 
                    WHERE train_number = %s AND day_of_week = %s AND available_ac_seats > 0
                    """
                    
                    berth_query = """
                    SELECT ts.ac_seats, ta.available_ac_seats
                    FROM train_seats ts, train_availability ta  
                    WHERE ts.train_number = %s AND ta.train_number = %s AND day_of_week = %s
                    """
                elif session['ticket_type']=="General":
                    update_seats_query = """
                    UPDATE train_availability 
                    SET available_gen_seats = available_gen_seats - 1 
                    WHERE train_number = %s AND day_of_week = %s AND available_gen_seats > 0
                    """

                    berth_query = """
                    SELECT ts.gen_seats, ta.available_gen_seats
                    FROM train_seats ts, train_availability ta  
                    WHERE ts.train_number = %s AND ta.train_number = %s AND day_of_week = %s
                    """
                cursor.execute(update_seats_query, (session['train_number'], datetime.strptime(session['travel_date'], "%Y-%m-%d").strftime('%A')))

                cursor.execute(berth_query, (session['train_number'], session['train_number'], datetime.strptime(session['travel_date'], "%Y-%m-%d").strftime('%A')))
                seats = cursor.fetchone()
                flash(seats)

                berth_no = seats[0]-seats[1]
                if session['ticket_type']=="AC":
                    coach_no = "A" + str(int(((berth_no-1)/50)+1))
                elif session['ticket_type']=="General":
                    coach_no = "G" + str(int(((berth_no-1)/50)+1))
                flash(coach_no)

                # Insert ticket details
                ticket_query = """
                INSERT INTO tickets (ticket_type, confirmation_status, departure_date, arrival_date, departure_time, arrival_time, ticket_ID, ticket_cluster, amount, coach_no, berth_no, ticket_source, ticket_destination)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """

                cursor.execute(ticket_query, (session['ticket_type'], 'Confirmed', session['travel_date'], session['arrival_date'], session['train_departure'], session['train_arrival'], ticket_id, session['ticket_cluster'], session['amount'], coach_no, berth_no, session['source'], session['destination']))

                # Insert MyTicket details
                myticket_query = """
                INSERT INTO MyTickets (UserId, ticket_ID)
                VALUES (%s, %s)
                """
                cursor.execute(myticket_query, (session['user'], ticket_id))

                # Insert booking details
                booking_query = """
                INSERT INTO booking (adhaar_number, ticket_ID)
                VALUES (%s, %s)
                """
                cursor.execute(booking_query, (session['adhaar_number'][i], ticket_id))

                # Insert reservation details
                reservation_query = """
                INSERT INTO reservation (ticket_ID, train_number)
                VALUES (%s, %s)
                """
                cursor.execute(reservation_query, (ticket_id, session['train_number']))

                connection.commit()
                flash(f"Booking successful! Your Ticket ID is {ticket_id}.")
            except Exception as e:
                connection.rollback()  # Rollback changes if there's an error
                flash(f"Booking failed: {str(e)}")  # Display error message
            finally:
                connection.close()

    return render_template('success.html', filename=session['ticket_cluster'])

@app.route('/ticket/ticket<filename>')
def ticket(filename):
    if (not session.get('user')):
        return redirect(url_for('login'))
    
    connection = get_db_connection()
    cursor = connection.cursor()
    
    passenger_query = """
    SELECT p.passenger_name, p.age, p.sex, t.coach_no, t.berth_no, t.ticket_ID
    FROM tickets t
    JOIN booking b ON b.ticket_ID = t.ticket_ID
    JOIN passengers p ON p.adhaar_number = b.adhaar_number
    WHERE ticket_cluster = %s
    """
    cursor.execute(passenger_query, (session['ticket_cluster'], ))
    passenger_details = cursor.fetchall()
    
    rendered = render_template('ticket.html', train_number=session['train_number'], train_name=session['train_name'], train_departure=session['train_departure'], train_arrival=session['train_arrival'], source=session['source'], destination=session['destination'], travel_date=session['travel_date'],
    arrival_date=session['arrival_date'], ticket_type=session['ticket_type'], amount=session['amount'], passengers=passenger_details)

    options = {
        'page-size': 'A3',
        'orientation': 'portrait',
        'margin-top': '0.5in',
        'margin-right': '0.5in',
        'margin-bottom': '0.5in',
        'margin-left': '0.5in',
        'encoding': "UTF-8",
        'custom-header': [
            ('Accept-Encoding', 'gzip')
        ],
        'no-outline': None
    }

    ticket = pdfkit.from_string(rendered,False, configuration=config, options=options)

    response = make_response(ticket)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=ticket{filename}.pdf'

    return response

if __name__ == '__main__':
    app.run(debug=True)
