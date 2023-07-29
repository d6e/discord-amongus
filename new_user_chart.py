from datetime import datetime

import pandas as pd
import plotly.express as px
from flask import Flask, render_template_string

app = Flask(__name__)


@app.route('/')
def index():
    df = pd.read_csv('data.csv')

    # Create additional columns for the hover data, converting Unix timestamp to ISO format
    df['Join_Date_Hover'] = df['Join_Date'].apply(lambda ts: datetime.utcfromtimestamp(ts).isoformat())
    df['Creation_Date_Hover'] = df['Creation_Date'].apply(lambda ts: datetime.utcfromtimestamp(ts).isoformat())

    # Create the scatter plot
    fig = px.scatter(df, x='Join_Date', y='Creation_Date', color='Set',
                     hover_data=['Member', 'Join_Date_Hover', 'Creation_Date_Hover'])

    # Customize the hover template
    fig.update_traces(
        hovertemplate=
        '<b>Member:</b> %{customdata[0]}' +
        '<br><b>Join Date:</b> %{customdata[1]}' +
        '<br><b>Creation Date:</b> %{customdata[2]}',
        # '<br><b>Set:</b> %{marker.color}<extra></extra>',
        marker=dict(size=2)
    )
    # convert the plotly plot to HTML representation
    plot_html = fig.to_html(full_html=False)

    # render the plot within a simple webpage
    return render_template_string(f"""
        <html>
        <head>
            <title>Interactive Plot</title>
        </head>
        <body>
            {plot_html}
        </body>
        </html>
        """)


if __name__ == '__main__':
    app.run(debug=True, port=5000)
