# ValueState

ValueState is a Flask-based smart real estate platform that predicts a property's fair price using a trained machine learning model and labels listings as Underpriced, Fairly Priced, or Overpriced.

## Features
- AI fair price prediction
- Property listing and image upload
- Deal rating and investment score
- Risk score and anomaly warnings
- Property inquiries and admin view
- Dashboard and analytics charts
- Price history tracking

## Project Structure
- `app.py` - main Flask application
- `database_setup.py` - creates database tables and sample data
- `bulk_insert_with_images.py` - inserts balanced demo listings with different images
- `model/` - trained ML model and model columns
- `templates/` - HTML templates
- `static/uploads/` - uploaded images
- `static/charts/` - generated charts

## Setup
1. Create and activate a virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Initialize the database:
   ```bash
   python database_setup.py
   ```
4. Run the app:
   ```bash
   python app.py
   ```
5. Open `http://127.0.0.1:5000/`

## Optional Demo Data
To insert more sample listings with different images:
```bash
python bulk_insert_with_images.py
```

## Notes
- Keep the `model/` folder in the project root.
- The model supports the trained Pune locations stored in `model_columns.pkl`.
- If your model was trained in a different Python environment, install matching package versions on the target system.
