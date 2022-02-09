import gc
import os
import pandas as pd
import plotly.graph_objs as go
from fpdf import FPDF


def add_plot_to_pdf(pdf, reference_gdf, geojson, col_name, title, colorscale='hot_r'):
    plot_df = reference_gdf.groupby(['zcta'])[col_name].mean().round().reset_index()
    
    fig = go.Figure(go.Choroplethmapbox(z=plot_df[col_name],
                                        locations=plot_df['zcta'], 
                                        colorscale=colorscale,
                                        colorbar=dict(thickness=20, ticklen=3),
                                        geojson=geojson,
                                        text=plot_df['zcta'],
                                        hovertemplate='<b>Zip code</b>: <b>%{text}</b>'+
                                                      '<br><b>' + col_name + '</b>: %{z}<br>',
                                        marker_line_width=0.1, marker_opacity=0.7))

    fig.update_layout(title_text=title, title_x =0.5, width=750, height=700,
                      mapbox=dict(style='open-street-map',
                                  zoom=9.7, 
                                  center = {"lat": pd.Series([point.y for point in reference_gdf.geometry]).mean() ,
                                            "lon":pd.Series([point.x for point in reference_gdf.geometry]).mean()},
                                  ))
    fig.write_image(col_name+'tmp.jpeg') 
    
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.image(col_name+'tmp.jpeg', x = None, y = None, w = 175, type = 'jpeg')
    
    os.remove(col_name+'tmp.jpeg')
    del fig, plot_df, reference_gdf, geojson, col_name, title, colorscale
    gc.collect()
    
    return pdf
    

def generate_pdf(reference_gdf, geojson):
    pdf = FPDF()
    
    pdf = add_plot_to_pdf(pdf, reference_gdf, geojson, 'response_time',
                          'Response times by zip code', 'hot_r')
    pdf = add_plot_to_pdf(pdf, reference_gdf, geojson, 'Per Capita Income', 
                          'Average per capita income by zip code', 'algae')
    
    # These plots are commented out to save memory on the free Heroku instance
    # pdf = add_plot_to_pdf(pdf, reference_gdf, geojson, 'Black', 
    #                       'Percentage of population who are Black by zip code', 'purp')
    # pdf = add_plot_to_pdf(pdf, reference_gdf, geojson, 'Hispanic/Latino Ethnicity', 
    #                       'Percentage of population who are Hispanic by zip code', 'purp')
    print(reference_gdf.shape)
    corr_df = reference_gdf.groupby(['zcta'])[['response_time', 'Per Capita Income', 
                                               'Black', 'Hispanic/Latino Ethnicity']].mean().corr().iloc[0, 1:]
    analysis_string = corr_df.to_string()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(txt=analysis_string)
    
    del reference_gdf, geojson, corr_df, analysis_string
    gc.collect()
    
    return pdf
