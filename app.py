import os
from flask import Flask, request, make_response, render_template
from werkzeug.utils import secure_filename
from fpdf import FPDF

import pandas as pd
import json
import geopandas as gpd
from geopandas.tools import sjoin
import plotly.graph_objs as go

UPLOAD_FOLDER = '/path/to/the/uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'csv', 'csv.zip'}

app = Flask(__name__, template_folder='templates')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = "super secret key"

zctas_df = gpd.read_file('tl_2020_us_zcta510.shp').to_crs(epsg=4326)
zctas_df_bounds = zctas_df.bounds
demographic_df = pd.read_csv('zip_data.csv')
demographic_df['Zip'] = [str(x).zfill(5) for x in demographic_df['Zip']]

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def upload_file():
   return render_template('upload.html')

@app.route('/uploader', methods=['GET', 'POST'])
def return_file():
    file = request.files['response_file']
    filename = secure_filename(file.filename)
    
    if filename[-8:] == '.csv.zip':
      df = pd.read_csv(file, compression='zip')
    elif filename[-4:] == '.csv':
      df = pd.read_csv(file)
    else:
      raise('File is not a .csv or .csv.zip file')
      
    print(df.shape)
    
    lat_col = request.form['lat_col']
    long_col = request.form['long_col']
    start_time_col = request.form['start_time_col']
    end_time_col = request.form['end_time_col']
    
    df[long_col] = df[long_col].astype(float, errors = 'raise')
    df[lat_col] = df[lat_col].astype(float, errors = 'raise')
    
    
    zctas_df_subset = zctas_df[((zctas_df_bounds.minx >= df[lat_col].min()) &\
                                (zctas_df_bounds.minx <= df[lat_col].max()) |\
                                (zctas_df_bounds.maxx >= df[lat_col].min()) &\
                                (zctas_df_bounds.maxx <= df[lat_col].max())) &\
                               ((zctas_df_bounds.miny >= df[long_col].min()) &\
                                (zctas_df_bounds.miny <= df[long_col].max()) |\
                                (zctas_df_bounds.maxy >= df[long_col].min()) &\
                                (zctas_df_bounds.maxy <= df[long_col].max()))]
    
    san_jose_zips = [95101, 95103, 95106, 95108, 95109, 95110, 95111, 95112, 95113, 95115, 95116, 95117, 95118, 95119, 95120,
             95121, 95122, 95123, 95124, 95125, 95126, 95127, 95128, 95129, 95130, 95131, 95132, 95133, 95134, 95135,
             95136, 95138, 95139, 95141, 95148, 95150, 95151, 95152, 95153, 95154, 95155, 95156, 95157, 95158, 95159,
             95160, 95161, 95164, 95170, 95172, 95173, 95190, 95191, 95192, 95193, 95194, 95196]
    san_jose_zips = [str(x) for x in san_jose_zips]
    
    zip_zcta_cross_df = pd.read_csv('Zip_to_zcta_crosswalk_2020.csv')
    zip_zcta_cross_df.ZIP_CODE = [str(x).zfill(5) for x in zip_zcta_cross_df.ZIP_CODE]
    zip_zcta_cross_df[zip_zcta_cross_df.ZIP_CODE.isin(san_jose_zips)].head()
    
    prior_len_df = len(df)
    df = df[df[[long_col, lat_col]].isnull().sum(axis=1) == 0].reset_index(drop = True)
    missing_lat_long = prior_len_df - len(df)
    print(missing_lat_long, 'rows missing latitude and/or longitude')
    
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[long_col], df[lat_col]))
    gdf.crs = zctas_df.crs
    bad_lat_long_value = ((gdf[long_col] > -84) | (gdf[long_col] < -179) |\
                          (gdf[lat_col] < 17) | (gdf[lat_col] > 72)).sum()
    print('Number of rows for which we are not expecting a match due to lat-longs not in the USA (often 0):', bad_lat_long_value)
    og_len = len(gdf)
    gdf = sjoin(gdf, zctas_df, how="inner")
    gdf = gdf[(gdf.Final_Incident_Category == 'Medical Only') & (gdf.Priority == 'Priority 1')]
    new_len = len(gdf)
    no_zip_match = og_len - new_len - bad_lat_long_value
    print('Number of rows with reasonable lat-longs dropped due to no match:', no_zip_match)
    
    gdf = pd.merge(gdf, demographic_df, how='left', left_on='ZCTA5CE10', right_on='Zip')
    print(gdf['Zip'].isnull().sum(), 'rows un-successfully matched with demographic data'.format(new_len))
    
    gdf['response_time'] = [x.seconds for x in pd.to_datetime(gdf[end_time_col]) -\
                            pd.to_datetime(gdf[start_time_col])]
    print((gdf[end_time_col].isnull() & ~gdf[start_time_col].isnull()).sum(), 
            'incidents are missing timestamp data due to no {} timestamp'.format(end_time_col))
    print((~gdf[end_time_col].isnull() & gdf[start_time_col].isnull()).sum(), 
            'incidents are missing timestamp data due to no {} timestamp'.format(start_time_col))
    print((gdf[end_time_col].isnull() & gdf[start_time_col].isnull()).sum(), 
            'incidents are missing timestamp data due to no {} or {} timestamps'.format(end_time_col, start_time_col))
    
    missing_timestamps = gdf['response_time'].isnull().sum()
    filtered_df_shape = len(gdf)
    gdf = gdf[~gdf['response_time'].isnull()].reset_index(drop = True)
    
    filtered_df_shape2 = len(gdf)
    LOWER_TIME_BOUND_SECONDS = 60
    UPPER_TIME_BOUND_SECONDS = 3600
    print((gdf['response_time'] < LOWER_TIME_BOUND_SECONDS).sum(), 'rows dropped due to response time shorter than a minute')
    print((gdf['response_time'] > UPPER_TIME_BOUND_SECONDS).sum(), 'rows dropped due to response time longer than an hour')
    response_time_out_of_range = ((gdf['response_time'] < LOWER_TIME_BOUND_SECONDS) | (gdf['response_time'] > UPPER_TIME_BOUND_SECONDS)).sum()
    gdf = gdf[(gdf['response_time'] >= LOWER_TIME_BOUND_SECONDS) & (gdf['response_time'] <= UPPER_TIME_BOUND_SECONDS)].reset_index()
    
    income_median = gdf['Per Capita Income'].median()
    black_median = gdf['Black'].median()
    hispanic_median = gdf['Hispanic/Latino Ethnicity'].median()
    print("Median zip-code-average income:", income_median)
    print("Median zip-code-level Black population proportion:", black_median)
    print("Median zip-code-average Hispanic population proportion:", hispanic_median)
    
    with open("san_jose_zctas.geojson") as geofile:
      zctas_df_geojson = json.load(geofile)
    
    for k in range(len(zctas_df_geojson['features'])):
      zctas_df_geojson['features'][k]['id'] = \
          zctas_df_geojson['features'][k]['properties']['ZCTA5CE10']

    plot_df = gdf.groupby(['ZCTA5CE10'])['response_time'].mean().reset_index()
    
    # To-do: investigate high response-time zip codes
    plot_df = plot_df[plot_df['response_time'] < 500]
    
    fig = go.Figure(go.Choroplethmapbox(z=plot_df['response_time'],
                                        locations=plot_df['ZCTA5CE10'], 
                                        colorscale='hot_r',
                                        colorbar=dict(thickness=20, ticklen=3),
                                        geojson=zctas_df_geojson,
                                        text=plot_df['ZCTA5CE10'],
                                        hovertemplate='<b>Zip code</b>: <b>%{text}</b>'+
                                                      '<br><b>Response time (seconds)</b>: %{z}<br>',
                                        marker_line_width=0.1, marker_opacity=0.7))

    # make note of filters for title text (ex. Fire - Priority 1 Medical)
    fig.update_layout(title_text ='Response times by zip code', title_x =0.5, width=750, height=700,
                      mapbox=dict(style='open-street-map',
                                  zoom=9.7, 
                                  center = {"lat": pd.Series([point.y for point in gdf.geometry]).mean() ,
                                            "lon":pd.Series([point.x for point in gdf.geometry]).mean()},
                                  ))
    fig.write_image("tmp.jpeg")
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.image("tmp.jpeg", x = None, y = None, w = 0, h = 0, type = 'jpeg')
    response = make_response(pdf.output(dest='S').encode('latin-1'))
    response.headers.set('Content-Disposition', 'attachment', 
                         filename=filename + '_analysis.pdf')
    response.headers.set('Content-Type', 'application/pdf')
    return response

if __name__ == "__main__":
    app.run(debug=False, port=60000)