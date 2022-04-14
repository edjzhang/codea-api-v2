# Emergency Response Time Open Data API
This repo implements the Open Data API referenced in this paper.

Open data users looking to answer questions related to equity struggle with the time-intensive process of bringing in appropriate demographic data to supplement existing datasets. In order to eliminate this barrier, our team developed an open U.S. Census-linked interface. This service provides a customizable workflow that connects existing government datasets to demographic information captured by the U.S. Census. For example, our interface uses latitude and longitude fields from public datasets to generate additional relevant data, such as county median household income level, education level, insurance coverage, race/ethnicity breakdown, etc. 

By augmenting local government datasets with demographic information, we can tackle equity-focused issues and more easily identify communities that local departments have historically underserved.

Those looking to answer specific questions related to resource equity must also develop analysis frameworks and visualizations to better understand the available data, which can pose another barrier to thorough equity analysis. To tackle this, our team built a proof-of-concept equity analysis playbook and visualization tool as a framework to understand local city datasets.

For this reason, we’ve established a set of equity analyses to quantitatively measure government service allocation and the quality of resources provided to different groups. These test for statistically significant differences in resource allocation across groups of zip codes, which are grouped by various demographic factors extracted from Census data, such as race/ethnicity, income, and more. We supplement these analyses with maps that visualize resource allocation and to start, quantitative demographic factors such as income. We focused on emergency response times as a measure of equity to demonstrate this open data standard and analysis framework.
