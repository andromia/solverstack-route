from . import bp

from flask import request, jsonify


@bp.route('/procedure', methods=['GET', 'POST'])
def main_procedure():
    """
    Main RPC endpoint for passing input data for optimized outputs.

    json expected: {
        "origin_latitude": "",
        "origin_longitude": "",
        "demand": {
            "latitude": [],
            "longitude": [],
            "units": [], # this will change with future iterations
            "unit_name": "",
            "cluster": []
        },
        "vehicles": [] # optional
    }
    """
    data = request.data

    return jsonify(data)