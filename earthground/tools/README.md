# Earthground Tools

## Place With KiCad

Run an Earthground design script, open KiCad, and continuously write a YAML
layout file while you move footprints or edit supported routed copper. The
file records placements, straight and arc tracks, through vias, and ordinary
single-layer copper zones.

Install Earthground, then run:

```
earthground kicad place your_design.py
```

Optional flags:

```
earthground kicad place your_design.py \
  --output placements.yaml \
  --poll-interval 1.0
```

The first board snapshot establishes a baseline and does not rewrite the YAML.
Subsequent supported changes are written atomically. Rule areas, zones with
holes or curved outlines, multilayer zones, and blind, buried, or microvias are
rejected rather than silently reduced to a less capable representation.
