from flask import Flask, render_template, request
import joblib
import pandas as pd

app = Flask(__name__)

# Load model
model = joblib.load("model/pune_house_price_model.pkl")
columns = joblib.load("model/model_columns.pkl")

def predict_price(location, sqft, bath, bhk):
    x = pd.DataFrame(columns=columns)
    x.loc[0] = 0
    
    x.loc[0, 'total_sqft'] = sqft
    x.loc[0, 'bath'] = bath
    x.loc[0, 'bhk'] = bhk
    
    loc_col = "site_location_" + location
    if loc_col in columns:
        x.loc[0, loc_col] = 1
    
    return model.predict(x)[0]

def price_recommendation(listed_price, predicted_price):
    difference = listed_price - predicted_price
    percentage_diff = (difference / predicted_price) * 100
    
    if percentage_diff < -10:
        return "Underpriced"
    elif percentage_diff > 10:
        return "Overpriced"
    else:
        return "Fairly Priced"

@app.route("/", methods=["GET", "POST"])
def home():
    result = None
    recommendation = None
    
    if request.method == "POST":
        location = request.form["location"]
        sqft = float(request.form["sqft"])
        bath = int(request.form["bath"])
        bhk = int(request.form["bhk"])
        listed_price = float(request.form["listed_price"])
        
        predicted_price = predict_price(location, sqft, bath, bhk)
        recommendation = price_recommendation(listed_price, predicted_price)
        
        result = round(predicted_price, 2)
    
    locations = [col.replace("site_location_", "") 
                 for col in columns if "site_location_" in col]
    
    return render_template("home.html",
                           result=result,
                           recommendation=recommendation,
                           locations=locations)

if __name__ == "__main__":
    app.run(debug=True)
