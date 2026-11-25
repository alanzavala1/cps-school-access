# Findings and methods

[Back to README](../README.md) · [Data sources](DATA_INVENTORY.md) ·
[Rebuild the analysis](../docs/DATA_PIPELINE.md)

These results describe the committed CPS SY2024–25 and ACS 2020–24 snapshot.
The unit is a census tract with an assigned neighborhood high school: 791 tracts
linked to 45 schools. Correlations describe area-level associations, not effects
on individual students. School outcomes reflect enrolled students and programs;
they do not isolate school effectiveness.

## Assigned-school outcomes

[`03_finding1.sql`](03_finding1.sql) compares tract median household income with
the SAT of the school assigned by the tract's Census internal point.
[`06_honesty_check.py`](06_honesty_check.py) also compares income, poverty, and
racial/ethnic composition and residualizes income and SAT against the controls.

| Comparison with assigned-school SAT | Pearson r | Tracts |
| --- | --- | --- |
| Median household income | +0.378 | 773 |
| Poverty rate | −0.391 | 789 |
| Black share | −0.529 | 789 |
| Hispanic share | +0.052 | 789 |
| Non-Hispanic white share | +0.555 | 789 |
| Income after controlling for poverty, Black share, and Hispanic share | −0.068 | 773 |

The positive income association is small after these controls. Income and
composition are correlated with each other, so these comparisons do not identify
independent causes. White share has the largest absolute bivariate correlation
in this table; reporting only Black share would omit part of the pattern.

The income correlations with attendance (+0.299) and chronic truancy (−0.230)
have the same directional interpretation. The mean of standardized SAT,
attendance, and inverted truancy correlates with income at +0.330. This
three-component check is separate from the six-component index used by the map.

Income and assigned SAT correlate at +0.517 when aggregated to one row per
assigned school, using the median income of its tracts. Many tracts share a
school outcome, so the tract rows are not independent school observations.
[`04_finding1_diagnostics.sql`](04_finding1_diagnostics.sql) provides income-decile
and truancy comparisons.

## Selective-school representation and proximity

[`07_finding2.sql`](07_finding2.sql) defines the selective set as high schools
with type `Selective enrollment` and a non-null SAT: 11 schools in this snapshot.
Representation uses summed student counts divided by summed enrollment, then
compares selective enrollment with all CPS high schools that have enrollment.

| Student group | Selective schools | All CPS high schools | Selective share / district share |
| --- | --- | --- | --- |
| Low-income | 47.8% | 72.5% | 0.66 |
| Black | 27.8% | 35.2% | 0.79 |
| Hispanic | 32.7% | 48.6% | 0.67 |
| White | 23.0% | 9.7% | 2.36 |

These are enrolled-student comparisons. They do not measure application rates,
offer rates, or the effect of an admissions policy.

The SQL also calculates straight-line distance to selective schools, counts
within three and five miles, and the SAT of the nearest selective. A subset with
SAT **≥1250** contains five schools; fields call this subset `elite`. This is a
project threshold, not an official CPS category. The separate **≥1010** threshold
is used for the map's nearest “strong school” comparison across all high schools.

[`08_combined.sql`](08_combined.sql) crosses assigned-school SAT and the SAT of
the nearest selective into value-based thirds. Identical values receive the
same tier, so group sizes are unequal.

| Combined status | Definition | Tracts |
| --- | --- | --- |
| Double disadvantage | Bottom third on both measures | 166 |
| Single disadvantage | Bottom third on one measure only | 262 |
| Middle | Remaining combinations | 249 |
| Double advantage | Top third on both measures | 114 |

This classification uses straight-line proximity and remains separate from
routed travel times and the community clustering layer.

## Travel-time definitions

Origins are tract Census internal points, not clicked addresses. OSRM uses a car
profile on the OSM road network. OpenTripPlanner 2.5.0 uses CTA GTFS and the OSM
walking network; trips can include walking, bus, rail, waits, and transfers.
Walk-only itineraries are allowed.

The committed transit matrix uses **July 8, 2026**, with departures at **7:00,
7:30, and 8:00 a.m.** For each departure the script chooses the shortest-duration
returned itinerary, then takes the median of available departure results. A
missing departure is omitted; no available departures produces a null duration.
This is a single summer service date, not a school-year average.

There are three distinct destination rules:

- Straight-line fields use geographic distance to a school.
- The panel's **nearest selective** and both selective routes use the school
  with the shortest road distance. Driving and CTA times refer to that same school.
- **Nearest top-tier** times minimize duration separately for each mode over
  selective schools with SAT ≥1250. The fastest destination can differ by mode.

[`18_routes.py`](18_routes.py) requests CTA path geometry at 7:30 a.m. Its route
label uses the median duration from the matrix, so the label need not equal the
duration of that particular itinerary. When precomputed routes are missing, the
frontend draws straight-line connectors from the clicked point.

### Results from the committed matrices

Transit to the fastest SAT ≥1250 selective has a median of **35.3 minutes**
(range **3.7–107.1**, 789 tracts). Driving has a median of **9.5 minutes**
(range **1.2–32.5**, 791 tracts). The median tract-level transit/driving ratio is
**3.7** across tracts with both values. This compares each mode's fastest
destination within the subset, which need not be the same school.

Grouping tracts by Black population share, mean driving time to this subset is
9.6 minutes in the lowest-share quartile and 15.7 in the highest-share quartile.
Grouping by transit time itself instead gives mean transit times of 18.2 minutes
in the shortest-time quartile and 55.6 in the longest-time quartile. These use
different groupings and should not be treated as one paired comparison.

| Tract characteristic vs transit minutes to fastest SAT ≥1250 selective | Pearson r | Tracts |
| --- | --- | --- |
| Non-Hispanic white share | −0.414 | 787 |
| Median household income | −0.362 | 771 |
| Hispanic share | +0.270 | 787 |
| Black share | +0.241 | 787 |
| Poverty rate | +0.143 | 787 |

Longer transit trips are associated with both Black and Hispanic population
shares. The negative income and white-share associations are larger in absolute
value. [`15_transit_access.py`](15_transit_access.py) reports all these axes;
[`16_routed_access.sql`](16_routed_access.sql) joins the matrices into tract exports.

## How the map summarizes an area

The map colors community areas using [five school-access groups](COMMUNITY_CLUSTERING.md).
Click targets are exported tracts, so selection requires a tract with an
assigned-school SAT even where a community polygon extends beyond that coverage.

The panel distinguishes schools physically inside an area from schools assigned
to its tracts. Local-school outcome averages give each school equal weight;
citywide reference values are school medians. Assigned outcomes and income use
tract medians; demographic percentages use unweighted tract means. The most
common assigned school is counted by tracts, not students. In the frontend, an
even-sized median uses the upper middle observation rather than averaging the
middle pair; SQL and the clustering preparation use interpolated medians.

Travel rows and displayed routes describe the clicked tract. The area summary
and local-school averages describe the community area. Neither is a
population-weighted estimate for the whole area.

[`11_distress.sql`](11_distress.sql) min-max normalizes SAT, graduation, college
enrollment, freshman on-track, attendance, and inverted truancy across assigned
tracts. Their available-component mean is `default_index`, oriented so higher
means more concern. `access_index` averages inverted nearest-selective SAT and
distance to the nearest SAT ≥1250 selective; both use straight-line proximity.
`distress` averages the two indices. Demographics and routed minutes do not
enter these indices or the community clustering.

The panel's benchmark comparisons use fixed constants: SAT 1010, graduation 87%,
and college enrollment 62%. These are hard-coded reference values with no source
vintage in the configuration, not updated national statistics.

## Coverage and limits

- The map covers 791 assigned tracts, not all Chicago addresses or all Cook County
  tracts. Internal-point assignment can differ from the boundary at a clicked
  address. Use an official school locator for an address-level assignment.
- Income is missing for 18 exported tracts; race and poverty for two. Missing
  income is concentrated in areas with higher Black shares and poverty, so
  complete-case correlations can have selection bias. ACS uncertainty is not
  propagated into the analysis.
- Twenty high schools have no SAT value after zero scores are treated as missing.
  Missing outcomes and competitive enrollment limit comparisons between schools.
- CTA routing excludes Metra and Pace. It uses schedules rather than observed
  reliability. OSRM estimates road-network travel without live traffic. Two
  tracts lack a transit time to the SAT ≥1250 subset in the committed matrix.
- Raw feeds and routing inputs are cached but not fully version-pinned. The
  committed exports support running the map; rebuilding with fresh downloads
  may produce different results. See [data provenance](DATA_INVENTORY.md#sources).
- The clustering is descriptive and depends on preprocessing and initialization.
  Its [validation and sensitivity checks](COMMUNITY_CLUSTERING.md#validation)
  identify limits that a correctness pass alone does not resolve.
