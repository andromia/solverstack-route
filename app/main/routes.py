from datetime import datetime
from flask import render_template, flash, redirect, url_for, request, g, \
    jsonify, current_app, make_response
from flask_login import current_user, login_required
from app import db
#from app.main.forms import EditProfileForm, PostForm, SearchForm, MessageForm
from app.models import User, Demand
from app.main import bp
from io import TextIOWrapper, StringIO
import csv

from ..utils import timestamp
from pyords.cluster.implementations import get_dbscan_clusters
from pyords.solver.implementations import get_many_ortools_solutions_dataframe 

import pandas as pd
from .. import __version__

ALLOWED_EXTENSIONS = {'csv'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@bp.before_app_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()

@bp.route('/', methods=['GET', 'POST'])
@bp.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    return render_template('index.html', title='Home')

@bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)

        file = request.files['file']

        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            user_id = current_user.get_id()
            current_time = timestamp()
            Demand.query.filter_by(user_id=user_id).delete()
            csv_file = TextIOWrapper(file, encoding='utf-8')
            csv_reader = csv.reader(csv_file, delimiter=',')
            columns = []
            for row in csv_reader: # assumes first row is field names
                columns = list(row)
                break
            # get position of uploaded fields for more dynamic storage population
            positions = {col: i for i, col in enumerate(columns)}
            for i, row in enumerate(csv_reader):
                if i > 0:  # upload values only (field names are first row)
                    demand = Demand(
                        latitude=row[positions['latitude']],
                        longitude=row[positions['longitude']],
                        weight=row[positions['weight']],
                        pallets=row[positions['pallets']],
                        upload_date=timestamp(),
                        user_id=user_id)
                    db.session.add(demand)
                    db.session.commit()

            return redirect(url_for('main.index'))
    return render_template('upload.html')

@bp.route('/cvrp', methods=['GET', 'POST'])
@login_required
def cvrp():
    if request.method == 'GET':
        user_id = current_user.get_id()
        demand = db.engine.execute('select * from demand '
            ' where demand.user_id = %s' % user_id).fetchall()
        data = [dict(row) for row in demand]
        
        df = pd.DataFrame(data)
        if df.empty:
            flash('upload data')
            return redirect(url_for('main.upload'))

        df = get_dbscan_clusters(df)
        df = get_many_ortools_solutions_dataframe(df, segmentation_col='cluster')

        enumerator = enumerate(df.vehicle.fillna('unassigned').unique())
        vehicle_mapping = {old: new for new, old in enumerator}
        df.vehicle = df.vehicle.replace(vehicle_mapping)
        df.vehicle = df.vehicle.replace({vehicle_mapping['unassigned']: 'unassigned'})
        df = df.sort_values(by='vehicle')
        solution = df.to_json(orient='records')

    return render_template('cvrp.html', data=data, solution=solution)

@bp.route('/download')
@login_required
def download():
    user_id = current_user.get_id()
    si = StringIO()
    csv_writer = csv.writer(si)
    cursor = db.engine.execute('select * from demand '
        ' where user_id = %s' % user_id)
    columns = cursor.keys()
    rows = cursor.fetchall()
    csv_writer.writerow(columns)
    csv_writer.writerows(rows)
    response = make_response(si.getvalue())
    response.headers['Content-Disposition'] = \
        'attachment; filename=solution.csv'
    response.headers['Content-type'] = 'text/csv'
    return response
