import os
from flask import Flask, request, make_response, render_template
from werkzeug.utils import secure_filename
from fpdf import FPDF

import pandas as pd
import json
import geopandas as gpd
from geopandas.tools import sjoin
import plotly.graph_objs as go

from data_cleaning import read_upload, clean_lat_long
# from generate_pdf import

app = Flask(__name__, template_folder='templates')
app.secret_key = "super secret key"

# 2010 Census ZCTA boundaries from https://earthworks.stanford.edu/catalog/stanford-dc841dq9031
zctas_df = gpd.read_file('data/dc841dq9031.shp').to_crs(epsg=4326)
zctas_df_bounds = zctas_df.bounds
# Demographic data from tack-data.com, cross-referenced for confirmation with
# https://github.com/edjzhang/zipbiaschecker where available
demographic_df = pd.read_csv('zip_data.csv')
demographic_df['Zip'] = [str(x).zfill(5) for x in demographic_df['Zip']]

@app.route('/')
def upload_file():
   return render_template('upload.html')

@app.route('/uploader', methods=['GET', 'POST'])
def return_file():
    file = request.files['response_file']
    filename = secure_filename(file.filename)
    
    df = read_upload(file, filename)
      
    print(df.shape)
    
    lat_col = request.form['lat_col']
    long_col = request.form['long_col']
    start_time_col = request.form['start_time_col']
    end_time_col = request.form['end_time_col']
    
    df, missing_lat_long_value, non_us_lat_long_value = clean_lat_long(df, lat_col, long_col)
    print(missing_lat_long_value, 'rows missing latitude and/or longitude')
    print(non_us_lat_long_value, 'rows with latitude and/or longitude outside of the US')
    
    
    zctas_df_subset = zctas_df[(((zctas_df_bounds.miny >= df[lat_col].min()) &\
                                (zctas_df_bounds.miny <= df[lat_col].max())) |\
                                ((zctas_df_bounds.maxy >= df[lat_col].min()) &\
                                (zctas_df_bounds.maxy <= df[lat_col].max()))) &\
                               (((zctas_df_bounds.minx >= df[long_col].min()) &\
                                (zctas_df_bounds.minx <= df[long_col].max())) |\
                                ((zctas_df_bounds.maxx >= df[long_col].min()) &\
                                (zctas_df_bounds.maxx <= df[long_col].max())))]
    print(zctas_df_subset.shape)
    
    # Sample 1000 only for the free Heroku deployment; if running locally, can remove this
    df = df.sample(1000)
    
    # Join incidents to zip codes
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[long_col], df[lat_col]))
    gdf.crs = zctas_df_subset.crs
    og_len = len(gdf)
    gdf = sjoin(gdf, zctas_df_subset, how="inner")
    new_len = len(gdf)
    no_zip_match = og_len - new_len - non_us_lat_long_value
    print('Number of rows with reasonable lat-longs dropped due to no match:', no_zip_match)
    
    # Join incidents to additional Census data
    gdf = pd.merge(gdf, demographic_df, how='left', left_on='zcta', right_on='Zip')
    print(gdf['Zip'].isnull().sum(), 'rows un-successfully matched with demographic data')
    
    # Calculate response time
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
    
    # Filter and flag unexpected response times
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
    
    zctas_df_subset = zctas_df_subset.to_crs(epsg=4326)
    zctas_df_subset.to_file("data/zctas_df_subset_tmp.geojson", driver = "GeoJSON")
    with open("data/zctas_df_subset_tmp.geojson") as geofile:
      zctas_df_geojson = json.load(geofile)
    
    for k in range(len(zctas_df_geojson['features'])):
      zctas_df_geojson['features'][k]['id'] = \
          zctas_df_geojson['features'][k]['properties']['zcta']

    plot_df = gdf.groupby(['zcta'])['response_time'].mean().round().reset_index()
    
    fig = go.Figure(go.Choroplethmapbox(z=plot_df['response_time'],
                                        locations=plot_df['zcta'], 
                                        colorscale='hot_r',
                                        colorbar=dict(thickness=20, ticklen=3),
                                        geojson=zctas_df_geojson,
                                        text=plot_df['zcta'],
                                        hovertemplate='<b>Zip code</b>: <b>%{text}</b>'+
                                                      '<br><b>Response time (seconds)</b>: %{z}<br>',
                                        marker_line_width=0.1, marker_opacity=0.7))

    fig.update_layout(title_text ='Response times by zip code', title_x =0.5, width=750, height=700,
                      mapbox=dict(style='open-street-map',
                                  zoom=9.7, 
                                  center = {"lat": pd.Series([point.y for point in gdf.geometry]).mean() ,
                                            "lon":pd.Series([point.x for point in gdf.geometry]).mean()},
                                  ))
    tmp_file_name = 'tmp_' + str(pd.Timestamp.now()) + '.jpeg'
    fig.write_image(tmp_file_name)
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.image(tmp_file_name, x = None, y = None, w = 100, type = 'jpeg')
    response = make_response(pdf.output(dest='S').encode('latin-1'))
    response.headers.set('Content-Disposition', 'attachment', 
                         filename=filename + '_analysis.pdf')
    response.headers.set('Content-Type', 'application/pdf')
    
    os.remove(tmp_file_name)
    
    return response

if __name__ == "__main__":
    app.run(debug=False, port=60000)