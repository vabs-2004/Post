from flask import Flask, request, jsonify
import pandas as pd
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
from flask_caching import Cache

app = Flask(__name__)

app.config["CACHE_TYPE"] = "SimpleCache"
app.config["CACHE_DEFAULT_TIMEOUT"] = 3600
cache = Cache(app)

file_path = "C:/Users/vaibh/delivery.csv"  
df = pd.read_csv(file_path)

df = df[['pincode', 'officename', 'district', 'statename', 'delivery', 'latitude', 'longitude']]

df['pincode'] = df['pincode'].astype(str)

df = df.dropna(subset=['latitude', 'longitude'])

df = df[df['delivery'].str.lower() == 'delivery']

df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')


geolocator = Nominatim(user_agent="geo_locator")

@cache.memoize(timeout=86400)  
def get_lat_lon(address):
    try:
        location = geolocator.geocode(address)
        if location:
            return location.latitude, location.longitude
    except Exception as e:
        print(f"Geolocation error: {e}")
    return None, None

def find_nearest_post_offices(address, user_pincode, num_offices=5):
    user_lat, user_lon = get_lat_lon(address)
    
    if user_lat is None or user_lon is None:
        return {"error": "Could not determine latitude and longitude for the given address."}

    pincode_offices = df[df['pincode'] == user_pincode]
    if not pincode_offices.empty:
        matched_office = pincode_offices.iloc[0]
        return {
            "nearest_office": {
                "officename": matched_office['officename'],
                "district": matched_office['district'],
                "state": matched_office['statename'],
                "pincode": matched_office['pincode'],
                "distance_km": 0  
            },
            "nearby_offices": []
        }

   
    df['distance'] = df.apply(
        lambda row: geodesic((user_lat, user_lon), (row['latitude'], row['longitude'])).km, axis=1
    )

    nearest_office = df.loc[df['distance'].idxmin()]

    
    nearby_offices = df.nsmallest(num_offices + 1, 'distance').iloc[1:]  

    nearby_offices_list = [
        {
            "officename": row['officename'],
            "district": row['district'],
            "state": row['statename'],
            "pincode": row['pincode'],
            "distance_km": round(row['distance'], 2)
        }
        for _, row in nearby_offices.iterrows()
    ]

    return {
        "nearest_office": {
            "officename": nearest_office['officename'],
            "district": nearest_office['district'],
            "state": nearest_office['statename'],
            "pincode": nearest_office['pincode'],
            "distance_km": round(nearest_office['distance'], 2)
        },
        "nearby_offices": nearby_offices_list
    }

@app.route('/predict', methods=['POST'])
def nearest_post_office():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request. Expected JSON body."}), 400

        address = data.get("address")
        user_pincode = str(data.get("pincode"))

        if not address or not user_pincode:
            return jsonify({"error": "Both address and pincode are required"}), 400

        result = find_nearest_post_offices(address, user_pincode)
        return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)  
