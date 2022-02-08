import gc
import os

import pandas as pd
import plotly.graph_objs as go
from fpdf import FPDF

def generate_plot_pdf(response_df, geojson, reference_gdf):
    fig = go.Figure(go.Choroplethmapbox(z=response_df['response_time'],
                                        locations=response_df['zcta'], 
                                        colorscale='hot_r',
                                        colorbar=dict(thickness=20, ticklen=3),
                                        geojson=geojson,
                                        text=response_df['zcta'],
                                        hovertemplate='<b>Zip code</b>: <b>%{text}</b>'+
                                                      '<br><b>Response time (seconds)</b>: %{z}<br>',
                                        marker_line_width=0.1, marker_opacity=0.7))

    fig.update_layout(title_text ='Response times by zip code', title_x =0.5, width=750, height=700,
                      mapbox=dict(style='open-street-map',
                                  zoom=9.7, 
                                  center = {"lat": pd.Series([point.y for point in reference_gdf.geometry]).mean() ,
                                            "lon":pd.Series([point.x for point in reference_gdf.geometry]).mean()},
                                  ))
    tmp_file_name = 'tmp.jpeg'
    fig.write_image(tmp_file_name)
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.image(tmp_file_name, x = None, y = None, w = 100, type = 'jpeg')
    
    os.remove(tmp_file_name)
    del fig, tmp_file_name, response_df, geojson, reference_gdf
    gc.collect()
    
    return pdf
