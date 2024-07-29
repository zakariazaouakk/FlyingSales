from flask import Flask, request, render_template, redirect, url_for
import pandas as pd
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

# Ensure the upload folder exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def replace_qualification(qual):
    if qual in ['Kiné', 'Kinésithérapeute','kiné', 'kinésithérapeute','kine','Kine']:
        return 'kine'
    elif qual in ['IDEL', 'IDEL TITULAIRE']:
        return 'idel'
    else:
        return qual

def categorize_time(call_time):
    hour = pd.to_datetime(call_time, format='%H:%M').hour
    if 9<= hour < 12:
        return 'MATIN:9h->12h'
    elif 12 <= hour < 14:
        return 'MIDI:12h->14h'
    elif 14 <= hour < 17:
        return ' DEBUT APRES-MIDI:14h->17h'
    elif 17 <= hour < 19:
        return 'FIN APRES-MIDI:17h->19'
    else :
        return 'SOIR'

def classify_sentiment(label):
    if any(keyword.lower() in label.lower() for keyword in ['repondeur', 'a relancer', 'rappel personnel','Cota DPC 2024 KO','contact via autre canal', 'accord', 'info secretaire ok']):
        return 'positif'
    elif any(keyword.lower() in label.lower() for keyword in ['refus', 'cota', 'cessation', 'ne plus appeler', 'hors cible']):
        return 'negatif'
    else:
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analysis', methods=['GET', 'POST'])
def analysis():
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)
        
        file = request.files['file']
        
        if file.filename == '':
            return redirect(request.url)
        
        if file:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            df = pd.read_csv(filepath)
            ND = df[['Qualification', 'Profession', 'Ville', 'Heure d\'appel']]
            ND['Profession'] = ND['Profession'].apply(replace_qualification)
            ND['Time'] = ND['Heure d\'appel'].apply(categorize_time)
            ND['Sentiment'] = ND['Qualification'].apply(classify_sentiment)
            ndf = ND.drop(['Heure d\'appel', 'Qualification'], axis=1)
            
            # Sentiment analysis
            sentiment_counts = ndf.groupby(['Ville', 'Profession', 'Sentiment']).size().unstack(fill_value=0)
            sentiment_counts['taux positif'] = sentiment_counts.get('positif', 0) / sentiment_counts.sum(axis=1)
            sentiment_counts['taux negatif'] = sentiment_counts.get('negatif', 0) / sentiment_counts.sum(axis=1)
            sentiment_counts = sentiment_counts.reset_index()
            
            # Optimal call times
            optimal_times = ND.groupby(['Ville', 'Profession', 'Time']).size().reset_index(name='Count')
            optimal_times = optimal_times.sort_values(by=['Ville', 'Profession', 'Count'], ascending=[True, True, False])
            optimal_times = optimal_times.groupby(['Ville', 'Profession']).head(1).reset_index(drop=True)
            
            sentiment_results = sentiment_counts.to_dict(orient='records')
            optimal_results = optimal_times.to_dict(orient='records')
            
            return render_template('analysis.html', sentiment_results=sentiment_results, optimal_results=optimal_results)

    return render_template('analysis.html', sentiment_results=[], optimal_results=[])

@app.route('/compare', methods=['GET', 'POST'])
def compare():
    if request.method == 'POST':
        if 'file' not in request.files or 'date1' not in request.form or 'date2' not in request.form:
            return redirect(request.url)
        
        file = request.files['file']
        date1 = request.form['date1']
        date2 = request.form['date2']
        
        if file.filename == '':
            return redirect(request.url)
        
        if file:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            df = pd.read_csv(filepath)
            df['Date d\'appel'] = pd.to_datetime(df['Date d\'appel'])
            date1 = pd.to_datetime(date1)
            date2 = pd.to_datetime(date2)
            
            # Define sentiment classification function
            def classify_sentiment(label):
                if any(keyword.lower() in label.lower() for keyword in ['repondeur', 'a relancer', 'rappel personnel', 'cota dpc 2024 ko', 'contact via autre canal', 'accord', 'info secretaire ok']):
                    return 'positif'
                elif any(keyword.lower() in label.lower() for keyword in ['refus', 'cota', 'cessation', 'ne plus appeler', 'hors cible']):
                    return 'negatif'
                else:
                    return 'neutre'  # Use 'neutre' if no sentiment found
            
            # Apply sentiment classification
            df['Sentiment'] = df['Qualification'].apply(classify_sentiment)
            
            df_date1 = df[df['Date d\'appel'] == date1]
            df_date2 = df[df['Date d\'appel'] == date2]
            
            def get_sentiment_counts(df):
                sentiment_counts = df.groupby(['Ville', 'Profession', 'Sentiment']).size().unstack(fill_value=0)
                total_counts = sentiment_counts.sum(axis=1)
                sentiment_counts['taux_positif'] = sentiment_counts.get('positif', 0) / total_counts
                sentiment_counts['taux_negatif'] = sentiment_counts.get('negatif', 0) / total_counts
                sentiment_counts = sentiment_counts.reset_index()
                return sentiment_counts
            
            sentiment_counts_date1 = get_sentiment_counts(df_date1)
            sentiment_counts_date2 = get_sentiment_counts(df_date2)
            
            results_day1 = sentiment_counts_date1.to_dict(orient='records')
            results_day2 = sentiment_counts_date2.to_dict(orient='records')
            
            return render_template('compare.html', results_day1=results_day1, results_day2=results_day2, date1=request.form['date1'], date2=request.form['date2'])

    return render_template('compare.html', results_day1=[], results_day2=[], date1=None, date2=None)

@app.route('/optimal_call_times', methods=['GET', 'POST'])
def optimal_call_times():
    if request.method == 'POST':
        if 'file' not in request.files or 'day' not in request.form:
            return redirect(request.url)
        
        file = request.files['file']
        day = request.form['day']
        
        if file.filename == '':
            return redirect(request.url)
        
        if file:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            df = pd.read_csv(filepath)
            df['Date d\'appel'] = pd.to_datetime(df['Date d\'appel'])
            df['Day'] = df['Date d\'appel'].dt.day_name()
            df['Time Interval'] = df['Heure d\'appel'].apply(categorize_time)
            
            def classify_sentiment(label):
                if any(keyword.lower() in label.lower() for keyword in ['repondeur', 'a relancer', 'rappel personnel', 'Cota DPC 2024 KO', 'contact via autre canal', 'accord', 'info secretaire ok']):
                    return 'positif'
                elif any(keyword.lower() in label.lower() for keyword in ['refus', 'cota', 'cessation', 'ne plus appeler', 'hors cible']):
                    return 'negatif'
                else:
                    return None
            
            df['Sentiment'] = df['Qualification'].apply(classify_sentiment)
            
            # Filter by the selected day
            df_filtered = df[df['Day'] == day]
            
            # Compute optimal time intervals
            if not df_filtered.empty:
                # Group by Ville, Profession, Time Interval and get the most common time interval
                optimal_times = df_filtered.groupby(['Ville', 'Profession', 'Time Interval']).size().reset_index(name='Count')
                optimal_times = optimal_times.sort_values(by=['Ville', 'Profession', 'Count'], ascending=[True, True, False])
                
                # Keep the top entry for each Ville and Profession
                optimal_times = optimal_times.groupby(['Ville', 'Profession']).head(1).reset_index(drop=True)
            else:
                optimal_times = pd.DataFrame(columns=['Ville', 'Profession', 'Time Interval', 'Count'])
            
            results = optimal_times.to_dict(orient='records')
            return render_template('optimal_call_times.html', results=results, day=day)
    
    return render_template('optimal_call_times.html', results=[], day=None)


if __name__ == '__main__':
    app.run(debug=True)
