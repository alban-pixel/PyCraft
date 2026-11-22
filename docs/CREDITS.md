# Credits of the Earth's data

The Earth mode plays on data that many surveys and agencies made and share. It resamples them and
adds small relief they don't have: it is a game, not a map, and not for navigation.

## Elevation: Terrain Tiles

[Terrain Tiles](https://registry.opendata.aws/terrain-tiles/), by Mapzen and Tilezen, hosted by the
AWS Open Data program, downloaded while you play. Changes: broken pixels are mended, the sea floor
comes from coarser tiles, the highest summits get their surveyed height back. Attribution asked by
[Tilezen](https://github.com/tilezen/joerd/blob/master/docs/attribution.md):

- ArcticDEM terrain data DEM(s) were created from DigitalGlobe, Inc., imagery and funded under
  National Science Foundation awards 1043681, 1559691, and 1542736;
- Australia terrain data © Commonwealth of Australia (Geoscience Australia) 2017;
- Austria terrain data © offene Daten Österreichs – Digitales Geländemodell (DGM) Österreich;
- Canada terrain data contains information licensed under the Open Government Licence – Canada;
- Europe terrain data produced using Copernicus data and information funded by the European Union –
  EU-DEM layers;
- Global ETOPO1 terrain data U.S. National Oceanic and Atmospheric Administration;
- Mexico terrain data source: INEGI, Continental relief, 2016;
- New Zealand terrain data Copyright 2011 Crown copyright (c) Land Information New Zealand and the
  New Zealand Government (All rights reserved);
- Norway terrain data © Kartverket;
- United Kingdom terrain data © Environment Agency copyright and/or database right 2015. All rights
  reserved;
- United States 3DEP (formerly NED) and global GMTED2010 and SRTM terrain data courtesy of the U.S.
  Geological Survey.

## Climate: CHELSA

CHELSA V2.1 climatologies 1981–2010 (CC0 1.0), averaged to 1/6 of a degree and brought to sea level
by `tools/make_climate.py`; the result is `pycraft/earth/climate.npz`. Karger, D.N., Conrad, O.,
Böhner, J., Kawohl, T., Kreft, H., Soria-Auza, R.W., Zimmermann, N.E., Linder, H.P., Kessler, M.
(2017): Climatologies at high resolution for the Earth's land surface areas. Scientific Data 4,
170122.
