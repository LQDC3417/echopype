ICES Journal of Marine Science,2024,Vol.81,Issue 10,1941–1951
https://doi.org/10.1093/icesjms/fsae133
Received: 12 March 2024;revised: 4 September 2024;accepted: 4 September 2024
Advanceaccesspublicationdate:9October 2024
Original Article
Interoperable and scalable echosounder data processing
with Echopype
Wu-Jung Lee 1,*,Landung Setiawan 2,Caesar Tuguinay 1,Emilio Mayorga 1,
Valentina Staneva 2
1 Applied Physics Laboratory,University of Washington,Seattle,WA98105,United States
2 eScience Institute,University of Washington,Seattle,WA98105,United States
∗Corresponding author.Applied Physics Laboratory,University of Washington,Seattle,WA98105,United State.E-mail:leewj@uw.edu
Abstract
Echosounders are high-frequency sonar systems used to sense fish and zooplankton underwater.Their deployment on a variety of ocean
observing platforms is generating vast amounts of data at an unprecedented speed from the oceans.Efficient and integrative analysis
of these data,whether across different echosounder instruments or in combination with other oceanographic datasets,is crucial for
understanding marine ecosystem response to the rapidly changing climate.Here we present Echopype, an open-source Python software
library designed to address this need. By standardizing data as labeled, multi-dimensional arrays encoded in the widely embraced
netCDF data model following a community convention,Echopype enhances the interoperability of echosounder data,making it easier
to explore and use.By leveraging scientific Python libraries optimized for distributed computing,Echopype achieves computational
scalability,enabling efficient processing in both local and cloud computing environments.Echopype’smodularizedpackagestructure
further provides a unified framework for expanding support for additional instrument raw data formats and incorporating new analysis
functionalities. We plan to continue developing Echopype by supporting and collaborating with the echosounder user community,
and envision that the growth of this package will catalyze the integration of echosounder data into broader regional and global ocean
observation strategies.
Keywords: echosounder; fisheries acoustics; water column sonar data; data standardization; distributed computing; cloud computing; open-source software
Introduction
matically expanded data collection capability, the fisheries
Active sonar systems are the workhorse for observing physi- acoustics and the broader ocean sciences communities are
cal, biological, and geophysical features associated with the just beginning to tap the full potential of these datasets. ICES
ocean due to their unique ability to collect data contin- Working Group on Global Acoustic Interoperable Network
uously at a wide range of resolution in time and space (GAIN)(2024).
(Medwin and Clay 1998). For measuring biological scat- Over the past decades, many software packages have
terers such as fish and zooplankton in the water column, been developed to streamline and improve the efficiency of
decades of research since the 1970s have culminated in the echosounder data processing (Table 1) (Echolab/PyEcholab:
regular use of scientific echosounder systems as a survey Wall et al. 2018, Echoview n.d., EchoviewR: Harrison et
tool for fisheries and marine ecological research (Stanton al. 2015, ESP3: Ladroit et al. 2020, LSSS: Korneliussen
2012). et al. 2006, Matecho: Perrot et al. 2018, MOVIES3D:
The recent successful integration of active sonar systems Trenkel et al. 2009). Most of these packages are operated
on a wide variety of ocean observing platforms (e.g. Suberg through a graphical user interface (GUI), allowing scien-
et al. 2014, Moline et al. 2015, Chu et al. 2019) and the tists to visually scrutinize and analyze data. These pack-
broader availability of broadband echosounders and multi- ages support instrument-generated raw data or the ICES
beam systems (e.g. Colbo et al. 2014, Demer et al. 2017)have HAC standard data exchange format (HAC; McQuinn and
created a deluge of ocean sonar data. From ships,moorings, Reid 2005) from multiple sonar systems (e.g. Echoview sup-
and autonomous vehicles, large volumes of data are accumu- ports over 70 file formats), and some offer real-time data
lating at an unprecedented speed from the oceans,including streaming from multiple instruments during a survey (e.g.
from previously inaccessible remote regions and the deep sea. MOVIES3D,LSSS,and Echoview).To handle large datasets,
For example, the NOAA National Centers for Environmen- some packages support out-of-core computation to pro-
tal Information (NCEI) in the US holds nearly 300 TB of cess data that is too large to fit into local memory (e.g.
water column sonar data as of July 2024,with this number Echoview, ESP3, LSSS). For reproducibility, many packages
growing rapidly (Wall et al.2016).In addition,data storage offer templates or scripts for automated or semi-automated
formats vary widely across manufacturer,instrument model, routine data processing that can be executed alongside
system design (e.g.single-beam,split-beam,multibeam),and manual analysis (e.g. Echoview, ESP3, LSSS). Some pack-
signaltype(e.g.broadbandvs.narrowband),makingitchal- ages further allow custom analysis through plug-in scripts
lengingto“wrangle”intocohesivedatasets.Despitethedra- (e.g. the Echoview code operator) or external integration
©The Author(s)2024.Publishedby Oxford University Pressonbehalfof International Councilforthe Explorationofthe Sea.Thisisan Open Access
articledistributedunderthetermsofthe Creative Commons Attribution License(https://creativecommons.org/licenses/by/4.0/),whichpermitsunrestricted
reuse,distribution,andreproductioninanymedium,providedtheoriginalworkisproperlycited.
Downloaded
from
https://academic.oup.com/icesjms/article/81/10/1941/7815946
by
Institute
of
Hydrobiology
user
on
17
June
2026

1942 Leeetal.
gnitsixellafoevitsuahxeebotdednetnitonsidnayrammusasielbatsihteto N.gnitirwfoemitehttagnissecorpatadrednuosohcerofsegakcaperawtfosdesuylnommochtiwepypohc Efonosirapmo C.1 elba T eromrofseivom/teefl/rf.remerfi.baltig//:sptthyrotisoperedocehtee S.ohceta Mhtiwbalta Mnidnad 3 seivomyphtiwnohty Pniesurofxuni Ldnaswodni Wnidelipmocebnacseludomgnissecorperoc D3 SEIVOMf (e.g.Matechoand EchoviewRthatleverage MOVIES3Dand
)dohceta M/D3 SEIVOM )eesnecilcimedacaeer F Echoview,respectively).Recently,as in many other scientific
fields,multipleopen-sourcesoftwarepackageshaveemerged
[e.g.echopy(open-ocean-sounding 2021),EchoviewR,ESP3,
balta M/++C Matecho,PyEcholab,and the upcoming open-source release
)fswodni W etir W/dae R
of LSSS(Korneliussenetal.2024)],providingresearcherswith
toolstheycanfreelyuse,customize,andcontributeto,accel-
IUG .)D3 SEIVOM-dna-SEMREH/seennod-sed-te-snoissim-ed-noitse G/erawtfos-draobpih S/seitilica F/ne/rf.euqihpargonaecoettofl.www//:sptth(etisbew D3 SEIVOMehtnonoitamrofniesnecilee Se eratingthecollectiveprogressofthecommunity.
o N o N
| .)mth.atad_ranos_rof_noitnevnoc_4 FDCten-RANOS_SECI/stamrof_elfi_reht O/stamro F_eli F/ecnerefe R/ple Hbe W/moc.weivohce.troppus//:sptth(sutatstsetalehtrofetisbewweivohc Eee Sb | Most | echosounder | | data processing | | software | packages | are |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ----------- | ---- | --------------- | ---- | --------------- | -------- | ------ |
| | monolithic | tools | that | contain | many | functionalities | | embed- |
Downloaded from https://academic.oup.com/icesjms/article/81/10/1941/7815946 by Institute of Hydrobiology user on 17 June 2026
xuni L,swodni W ded in a single large, indivisible structure tightly linked to
| | a GUI. While | effective | | for visualizing | | data | and | performing |
| --- | ------------ | --------- | --- | --------------- | --- | ---- | --- | ---------- |
)cyrateirpor P yromem(se Y
pre-definedanalyses,thissetupcanbehardtoadaptfornew
)gnippam
| | research | needs. | Researchers | | often | start with | a | GUI pack- |
| --- | -------- | ------ | ----------- | --- | ----- | ---------- | --- | --------- |
SSSL dae R
ava J IUG age for initial data processing, then export the processed
o N
| | data for | further | analysis | elsewhere, | | such | as in another | soft- |
| --- | -------- | ----------- | -------- | ----------- | --- | ---- | ------------- | -------- |
| | ware or | a computing | | environment | | with | another | program- |
)TIM(ecruosnep O
| | ming language. | | Even | with open-source | | code, | GUI | programs |
| --- | -------------- | --- | ---- | ---------------- | --- | ----- | --- | -------- |
mroftalp-ssor C are time-consuming to modify due to their complex struc-
yromem(se Y
| | tures. In | contrast, | packages | | that operate | | primarily | via Ap- |
| --- | --------- | --------- | -------- | --- | ------------ | --- | --------- | ------- |
)gnippam
plication Programming Interfaces(APIs),suchas EchoviewR
balta M
3 PSE dae R and PyEcholab, offer greater flexibility for customization
IUG
o N and extensions. While some packages can utilize all proces-
| | sors, memory, | | and disk | resources | | on a local | machine | (e.g. |
| --- | ------------- | --- | -------- | --------- | --- | ---------- | ------- | ----- |
weivohc Eaiv,etir W/dae R
| | LSSS, Echoview), | | no | previous | packages | | can fully | leverage |
| --- | ---------------- | --- | --- | -------- | -------- | --- | --------- | -------- |
.liatedrof”ataddetrevnoc-warfoerutcurt S“noitce See S.0.1 vnoitnevnoc 4 FDCten-RANOSfonoitatpadanaswollofepypohc Ea
,)3-LPG(ecruosnep O the vastly scalable computing resources and flexible infras-
weivohc Eseriuqer IPAcitammargor P )weivohc Eaiv(se Y tructure offered by modern cloud technology (Vance et al.
mroftalp-ssor C 2019). Specifically, the inherent tightly integrated nature of
GUI-basedpackagescancomplicateeffortstodevelopcloud-
Rweivohc E
interfacingcapabilities,asallinterlinkingcomponents—from
dataingestion,processing,visualization,tostorage—mustbe
o N changed.
R
Inthispaper,wepresent Echopype,anopen-source Python
)ksidotdaoflfo(se Y softwarepackagedesignedforinteroperableandscalablepro-
| | cessing of | echosounder | | data | on both | local | and | cloud plat- |
| --- | ---------- | ----------- | --- | ---- | ------- | ----- | --- | ----------- |
)betir W/dae R forms.Drawinginspirationfromexistingpackages,Echopype
yrateirpor P
weivohc E swodni W .nmulocemasehtotnidenibmocsieroferehtdnaetarepoot D3 SEIVOMseriuqerohceta Md provides a uniform API for processing data from different
echosounderinstrumentsandoperatesbasedonstandardized
++C
IUG data. Unlike existing packages, however, Echopype is built
o N .)4202.latenessuilenro K(5202 niecruosnepootgninoitisnarttratsotsnalp SSSLc
| | on cutting-edge | | Python | libraries | for | distributing | | and cloud |
| --- | --------------- | --- | ------ | --------- | --- | ------------ | --- | --------- |
balohc Ey P/balohc E )TIM(ecruosnep O computing from the Pandata stack and is an integral com-
IPAcitammargor P
| | ponent of | the scientific | | Python | ecosystem. | | This | allows users |
| --- | --------- | -------------- | --- | ------ | ---------- | --- | ---- | ------------ |
nohty P/balta M mroftalp-ssor C
| | to rapidly | prototype | new | algorithms | | and | data | pipelines us- |
| --- | ------------- | ------------- | ------ | ------------ | ------- | --- | -------- | ------------- |
| | ing functions | both | within | and | outside | of | Echopype | without |
| | changing | the computing | | environment. | | By | natively | interfac- |
ingwithdifferentcomputinginfrastructures,Echopypework-
o N o N o N
flowdevelopedonapersonallaptopcanbeseamlesslyported
| | to platforms | with | much | larger | computing | | resources, | such |
| --- | ------------ | ---- | ---- | ------ | --------- | --- | ---------- | ---- |
)0.2 ehcap A(ecruosnep O
| | as the cloud | or | an on-premise | | high-performance | | | computing |
| --- | ------------ | --- | ------------- | --- | ---------------- | --- | --- | --------- |
(HPC)cluster,withoutcodechanges.Thiscapabilityisunique
IPAcitammargor P
to Echopypeamongallcurrentechosounder data processing
mroftalp-ssor C
software.
)aetir W/dae R
| | In Section | “The | Echopype | | package,” | we | discuss | the de- |
| --- | ---------- | ---- | -------- | --- | --------- | --- | ------- | ------- |
epypohc E
signphilosophyof Echopype,detailtheadvantagesofourap-
nohty P
| se Y se Y | proachtostandardizingdatabeforeperformingdownstream | | | | | | | |
| ------- | --------------------------------------------------- | --- | --- | --- | --- | --- | --- | --- |
computations,anddescribethepackagestructureandcurrent
| | functionalities. | | In Section | “Use | case | examples,” | | we present |
| --- | ---------------- | --- | ---------- | ---- | ---- | ---------- | --- | ---------- |
.segakcaperawtfos 4 FDCten-RANOS fiveusecaseexamplesasexecutable Jupyter Notebooksusing
metsysgnitarep O
| | publicly | available | data | sources. | In | Section | “Discussion,”we | |
| --- | -------- | --------- | ---- | -------- | --- | ------- | --------------- | --- |
resuyramir P noitatupmoc
atadduol C noitcaretni eroc-fo-tu O .noitamrofni discussthecurrentadoptionof Echopype,itsexpansionflex-
egaugna L
ecafretni ibility,andthenextstageofdevelopmentgoals.Weconclude
esneci L troppus
| | the paper | by summarizing | | | the contributions | | of | Echopype |
| --- | ---------------- | -------------- | --------- | --- | ----------------- | ------- | ------------ | -------- |
| | to the fisheries | | acoustics | and | the | broader | oceanography | |

Interoperable and scalableechosounder data processingwith Echopype 1943
community, both as an open-source software tool and as a datawithechogrammorphologyanalysis,developdeeplearn-
communityforumcreatedthroughthepubliclyhostedonline ing algorithms, or incorporate oceanographic data such as
| coderepository. | | | | | | | | chlorophylllevelsandwatermassproperties. | | | | | | | |
| --------------- | --- | ------- | --- | --- | --- | --- | --- | ---------------------------------------- | ---------- | ------ | ----------- | ----- | ----------- | ------ | ----------- |
| | | | | | | | | Echopype’s | built-in | | scalability | gives | researchers | | the ability |
| | | | | | | | | to rapidly | prototype | and | experiment | | with | custom | analysis |
| The Echopype | | package | | | | | | | | | | | | | |
| | | | | | | | | routines | on a local | laptop | computer, | | and use | the | same code |
Designphilosophy on powerful computing clusters for full-scale analysis. This
| | | | | | | | | streamlined | development-to-deployment | | | | process | is | also ben- |
| ---------- | ----------- | --- | --------- | --------- | -------- | --------------- | ---------- | ----------- | ------------------------- | -------- | --- | -------------- | ------- | ---------- | --------- |
| The design | of Echopype | | is driven | by | the goal | of | creating a | | | | | | | | |
| | | | | | | | | eficial for | data | managers | and | data engineers | | generating | and |
| software | tool that | can | serve as | a conduit | for | scalable,inter- | | | | | | | | | |
operable, accessible, and reproducible computational work- servingmassivedatasets.However,notethat Echopypeisnot
Downloaded from https://academic.oup.com/icesjms/article/81/10/1941/7815946 by Institute of Hydrobiology user on 17 June 2026
flowsforechosounderdata.Theserequirementsareessential designed for manual data analysis, such as visual echogram
| | | | | | | | | scrutinization.The | | many | existing | GUI-based | | software | pack- |
| ------------ | --- | ------- | ------- | ---- | ------ | --- | -------- | ------------------ | --- | ---- | -------- | --------- | --- | -------- | ----- |
| for handling | the | rapidly | growing | data | volume | and | enabling | | | | | | | | |
agesarebettersuitedforthesetasks.
| integrative | use of | echosounder | | data | in fisheries | acoustics | as | | | | | | | | |
| ----------- | ------ | ----------- | --- | ---- | ------------ | --------- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
wellasmultidisciplinaryoceanographicresearch.
| (cid:2) | | | | | | | | Generalworkflow | | | | | | | |
| ------- | --- | --- | --- | --- | --- | --- | --- | --------------- | --- | --- | --- | --- | --- | --- | --- |
Scalable:Echopypeisdesignedtoscaleeffortlesslyfrom
| | | | | | | | | To achieve | the | above | goals, | we developed | | a workflow | that |
| --- | --- | --- | --- | --- | --- | --- | --- | ---------- | --- | ----- | ------ | ------------ | --- | ---------- | ---- |
asinglelaptoptoalargeclusterofcomputingnodeson
focusesfirstonstandardizingdataintowidelyused,openfor-
| an | HPC or | on the | cloud. | This | allows | users | to flexibly | | | | | | | | |
| --- | ------ | ------ | ------ | ---- | ------ | ----- | ----------- | --- | --- | --- | --- | --- | --- | --- | --- |
mats,andbuildcomputationalroutinesthatleveragecutting-
leveragecomputingresourcesmatchingtheirneeds,from
| | | | | | | | | edge Python | libraries | to | perform | distributed | | computing | and |
| ------- | ---- | ----------- | --- | ------------- | --- | ----------- | ------ | ----------- | --------- | --- | ------- | ----------- | --- | --------- | --- |
| initial | data | exploration | | to extensive, | | large-scale | analy- | | | | | | | | |
out-of-corecomputation(computationsthataretoolargeto
| ses. | In parallel, | we | aim | to support | the | human | dimen- | | | | | | | | |
| ---- | ------------ | --- | --- | ---------- | --- | ----- | ------ | --- | --- | --- | --- | --- | --- | --- | --- |
fitintoacomputer’smainmemory)basedonthesestandard-
sionofscalabilitybyensuringthatthesoftwareisuser-
| | | | | | | | | ized datasets | (Fig. | 1). | This design | allows | Echopype | | to flex- |
| -------- | -------- | ---------- | ------ | ----------- | ------- | -------------- | --------- | ------------- | ----- | ------- | ----------- | --------- | --------- | ------------- | --------- |
| friendly | for | individual | | researchers | working | | on small- | | | | | | | | |
| | | | | | | | | ibly handle | both | local | and cloud | computing | | environments, | |
| scale | projects | and | easily | shareable | for | community-wide | | | | | | | | | |
| | | | | | | | | and ensures | its | natural | continuing | | evolution | with | state-of- |
collaborationacrossmultiplegroups.
(cid:2) the-art computing technologies. Additionally, the standard-
| Interoperable: | | Echopype | | is | designed | to | integrate | | | | | | | | |
| -------------- | --- | -------- | --- | --- | -------- | --- | --------- | --- | --- | --- | --- | --- | --- | --- | --- |
izeddatasetsgeneratedby Echopypecanhelpexpandtheuse
| smoothly | | with other | software | | packages | in | the sci- | | | | | | | | |
| -------- | --- | ---------- | -------- | --- | -------- | --- | -------- | --- | --- | --- | --- | --- | --- | --- | --- |
ofechosounderdatafromasmallcommunityoffisheriesand
| entific | Python | ecosystem, | | including | | tools | from the | | | | | | | | |
| ------- | ------ | ---------- | --- | --------- | --- | ----- | -------- | --- | --- | --- | --- | --- | --- | --- | --- |
marinescientistswhoarealreadyusingthesedatatoabroader
| rapidly | advancing | | fields | of machine | learning | | and artifi- | | | | | | | | |
| ------- | --------- | --- | ------ | ---------- | -------- | --- | ----------- | --- | --- | --- | --- | --- | --- | --- | --- |
groupofoceanresearchers.Thedetailsofthesechoicesarede-
| cial | intelligence.By | | utilizing | standardized | | data | formats | | | | | | | | |
| ---- | --------------- | --- | --------- | ------------ | --- | ---- | ------- | --- | --- | --- | --- | --- | --- | --- | --- |
scribedbelow.
widelyusedinthegeosciencedomain(see Section“Data
| standardization”), | | | we enable | | the easy | combination | of | | | | | | | | |
| ------------------ | --- | --- | --------- | --- | -------- | ----------- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
Datastandardization
echosounderdatawithotheroceanographicdatatypes,
broadening its usage beyond the immediate fisheries The first stage of the Echopype workflow is data standard-
acousticscommunity. ization, which enables data interoperability across different
(cid:2)
Accessible: Echopype is platform-agnostic and can be echosounderinstrumentsandbetweenechosounderdataand
used on different operating systems and computing in- otheroceanographicdatasets.Thisinvolvesparsingandcon-
| | | | | | | | | verting | raw instrument-generated | | | files | into | a format | that |
| ------------- | --- | ------ | --- | ---------- | --- | ------ | -------- | ------- | ------------------------ | --- | --- | ----- | ---- | -------- | ---- |
| frastructure, | | making | it | accessible | to | a wide | range of | | | | | | | | |
users. Through use of open and widely used data for- conforms to an Echopype-adapted version of the Interna-
mats(net CDFand Zarr),dataproductsgeneratedfrom tional Councilforthe Explorationofthe Sea(ICES)SONAR-
Echopype remain accessible and usable outside of the net CDF4 v 1.0 convention (Macaulay and Peña 2018). This
Python software ecosystem, allowing users to leverage conventionusesthehierarchical,self-describingnet CDFdata
modelandtheassociated Climateand Forecast(CF)conven-
thetoolsthatbestsuittheirneeds.
(cid:2)
Reproducible: Echopype is designed with reproducible tions (Hassell et al. 2017, CF Metadata Conventions n.d.,
workflows in mind, offering APIs that can be flexibly Unidata n.d.) widely embraced by the physical and biogeo-
combined with custom functions defined by users. By chemicaloceancommunitiesoverthelasttwodecades(Snow-
providingtoolsthatareeasytouseinthe Jupyterenvi- den et al.2019,Tanhua et al.2019).SONAR-net CDF4 was
initiallydevelopedtostoreandexchangerawbackscatterand
| ronment | (Jupyter | | n.d.),where | | researchers | can | integrate | | | | | | | | |
| ------- | -------- | --- | ----------- | --- | ----------- | --- | --------- | --- | --- | --- | --- | --- | --- | --- | --- |
code, visualizations, and text explanations in a single ancillary data from ship-mounted, omni-directional sonars.
executable document (a Jupyter Notebook), Echopype The recent v 2.0 update added new data variables to accom-
contributes to and promotes transparent and repro- modate echosounder and acoustic Doppler current profiler
ducibleresearchinvolvingechosounderdata. (ADCP)data.Sincemost Echopypedatastandardizationfunc-
tionsweredevelopedpriortov 2.0,thedatastructureprimar-
Echopype’s strength lies in its flexibility through the pro- ily follows v 1.0 definitions.However,we included modifica-
grammatic APIandbeinganintegralcomponentofthescien- tions to support a gridded data structure for raw data (see
tific Python ecosystem.Unlike the many existing monolithic Section“Structureofraw-converteddata”)andadoptedv 2.0
GUI software, Echopype is designed to be fully “composi- namesfordatavariablesnotpresentinv 1.0.
tional,” allowing users to select and combine only the nec- Notethatthisapproachtostandardizedatabeforefurther
essaryfunctionsandcombinethemwiththosefromothersci- processing is similar to the approach taken by MOVIES3D
entific Python packages to meet specific research needs.This (Trenkel et al. 2009), which converts all echosounder data
adaptability suits the dynamic nature of scientific research to the ICES HAC format (McQuinn and Reid 2005)
(Bednarand Durant 2023).Forexample,inasinglecomput- beforeprocessingandvisualization.However,unlikenet CDF,
ingenvironment,researcherscaneasilyinterfaceechosounder HAC is not widely used in the broader geoscience domain

1944 Leeetal.
Figure 1.The Echopypeworkflow.Echopypeconvertsrawechosounderdataintostandardizednet CDFdatasetsandincorporatesancillarydata(e.g.
environmentalparameters,GPSpositions,andplatformmovementslikeroll,pitch,andheave)followingthe SONAR-net CDF4 convention.These
datasetscanbeserializedintothenet CDFor Zarrformats.Oncethestandardizeddataarecalibratedintophysicalquantities(e.g.volumebackscatter
strength,or Sv),thedataarerepresentedasgenericandflexible Xarraydatasets.
andlacksthecomputationaladvantageofferedbythecloud- Echopypeimplementsamodificationto SONAR-net CDF4
optimized Zarr format (Zarr n.d.), which can back-end the v 1.0 definitions to optimize data access and filtering (“slic-
net CDFdatamodel. ing”)efficiencyandusabilitybyorganizingpotentiallyragged
Processed data beyond the raw data level,such asvolume data records into a gridded structure.This modification pre-
backscattering strength [Sv, unit: d B re 1 m−1 (Mac Lennan datedthedevelopmentofthe Griddedgroupinthev 2.0 con-
et al. 2002)], are represented using a net CDF data model vention.
via a generic Xarray dataset. The processed datasets in- Thev 1.0 conventiondefinesacousticdatavariables,suchas
clude some metadata and ancillary data, such as calibra- backscatter_r,basedonaone-dimensionalraggedarray
tion parameters and environmental parameters that are crit- structure (Fig. 3 a) that uses a custom variable-length vector
ical in producing the Sv. The Australia Integrated Marine datatype(sample_t)andping_timeasitscoordinatedi-
Observing System (IMOS) SOOP-BA program published a mension.Echopyperestructuresthismulti-groupraggedarray
well-described processed data net CDF convention (Kunnath representationintoasingle-group,multi-dimensionalgridded
et al. 2018). A Gridded group was also introduced in the representation (Fig. 3 b) by introducing two new coordinate
SONAR-net CDF4 v 2.0 conventionforprocesseddata.While dimensions, range_sample and channel. Data from dif-
processed datasets generated by Echopype do not currently ferenttransducerchannelsaremappedalongthenewchan-
adhere to these definitions nor the ICES WGFAST Topic nel dimension, and data from each ping found in a sam-
Group (TG-Ac Meta) (2016) convention for metadata, the ple_t vector in the convention are mapped along the new
major data dimensions are similar and the differences are range_sample dimension. To handle potentially uneven
self-explanatory, due to the generality in echosounder data sample counts across pings or transducer channels, shorter
use cases. For example, the v 2.0 Gridded group data vari- data records are padded with Na N (Not a Number), cre-
able integrated_backscatter has coordinate dimen- ating a consistent gridded structure across all dimensions.
sions (ping_axis, range_axis, frequency), which This data storage variant can be losslessly transformed into
map to Echopype coordinate dimensions (ping_time, the contiguous ragged-array form defined in the convention
range_sample, channel)inthecalibrated Svdatasets. and is equivalent to the CF convention’s “incomplete multi-
Buildingonthenet CDFdatamodelin Echopype,boththe dimensional array”feature type (Eaton et al. n.d.). In prac-
raw-converted data and the processed data can be serialized tice, we have found that the Na N-padded data are com-
(saved) into the net CDF (.nc) format or the cloud-optimized pressedefficientlyanddonotincursubstantiallylargerstorage
Zarr (.zarr) format.In particular,the use of the Zarr format footprints.
underlies Echopype’sabilitytoscalecomputationflexiblywith In Echopype, the dimension and coordinate name chan-
datavolume(see Section“Interoperabilityandscalability”for nel is used rather than frequency to accommodate con-
detail).Weplantocontinueupdating Echopype’srawandpro- figurations in which multiple transducers of the same nomi-
cessed data formats as the community conventions continue nal frequency are used,because (1) duplicate values in a co-
toevolveandconverge. ordinate is not allowed, and (2) it is inaccurate to describe
echo data from broadband transmissions using a single fre-
Structureofraw-converteddata quency.Weaddedanewdatavariablefrequency_nominal
In Echopype,theraw-converteddataareencapsulatedinthe to capture the nominal operating frequency of a given
Echo Dataobjectcontainingthegroupsdefinedin SONAR- transducer channel that is often referred to by fisheries
net CDF4 (Fig. 2). An Echo Data object represents data acousticians.
fromoneechosounderinstrumentononeplatform.Multiple Note that Echopype interprets the convention v 1.0 def-
Echo Dataobjectscanbecombinedtoencapsulatedatafrom inition of the coordinate dimension beam that represents
anentiresurveyordeployment(viathecombine_echodata different sonar beams as comparable to different sectors of
function,see Section“Dataconversion”). split-beam transducers. Currently, this beam dimension is
Downloaded
from
https://academic.oup.com/icesjms/article/81/10/1941/7815946
by
Institute
of
Hydrobiology
user
on
17
June
2026

Interoperable and scalableechosounder data processingwith Echopype 1945
Figure 2.Anexamplerenderingofthe Echo Dataobjectthatmakesitconvenienttoinspectandaccessraw-converteddatastructuredaccordingtothe
Echopypeadaptationofthe SONAR-net CDF4 convention.Thedatasetrenderedherewasfroma Kongsberg Simrad EK80 echosounderconfiguredto
collectbothcomplexandpower-anglesamples.Seethe Echopypepackagedocumentationandtheechopype-examplesrepositoryforotherexamples.
Notethatonlythebeginningportionoflongdatavariablenamesisrenderedbydefault,butthefullvariablenamesarerevealedwhenthemouseis
hoveredoverinthe Jupyter Notebookenvironment.
Downloaded
from
https://academic.oup.com/icesjms/article/81/10/1941/7815946
by
Institute
of
Hydrobiology
user
on
17
June
2026

1946 Leeetal.
lennahc
SONAR-net CDF4 echopype
(a) sample_t (b) (v 0.9.0)
...
...
ping_time(0) ping_time(1) ping_time(2)
...
range_sample
puorg_mae B
e
m
_ti
g n pi
...
Figure 3.Representationofmulti-dimensionalechosounderbackscatterdata.(a)The SONAR-net CDF4 conventiondefinesaone-dimensional
contiguousraggedarraystructurewithdifferenttransducerchannelsindifferentgroups,ping_timeasthedimension,andalong-rangevaluesencoded
usingthecustomsample_tvariable-lengthvectordatatype.(b)Echopypeusesthe“incompletemultidimensionalarray”representationofthe CF
convention,withtransducerchannelsmappedalongthechanneldimensionandalong-rangevaluesmappedalongtherange_bindimension,inaddition
totheoriginalping_timedimension.Shorterpingsarepaddedwith Na Nvalues(darkercubes).Notethatthebeamdimensionforsplit-beamtransducers
isnotshownintheexamplesketchedhere.
present only when such data are available, such as when multi-dimensional data with physically meaningful coordi-
complexsamplesarerecordedbya Kongsberg Simrad EK80 nates,such as frequency,time,range,and geographical loca-
echosounder. In other cases, this dimension is implicit (not tion,alltypicalforechosounderdatasets.
present). A new coordinate dimension subbeam was intro- These packages also directly underlie Echopype’s unique
duced in convention v 2.0 to allow storing data from split- abilitytonativelyinterfacewithdataaccess,storage,andcom-
beam transducers,and its use is equivalent to the Echopype putationinaplatform-agnosticmanner,suchthatcodedevel-
beamdimensiondescribedhere. oped for local machines can be directly used with a scalable
computinginfrastructure(e.g.thecommercialcloud)without
Interoperabilityandscalability theneedtoreorganizedatasetsorrewritealgorithms.Toour
Echopype’sapproachtostandardizingrawandprocessedac- knowledge,Echopypeistheonlypackageofferingthiscapa-
tive acoustic data using the net CDF data model facilitates bilityamongallcurrentechosounder data processingsoftware
intuitive, user-friendly exploration and use of data in an packages(see Table I).
instrument-agnosticmanner,asthisdatamodeliswidelyem-
braced in the geoscience domain. This standardization also
directly enables computational interoperability and scalabil- Softwareengineeringpractices
itybyleveragingthreetightlycoupledopen-source Pythonli-
Echopype is developed with software engineering best prac-
brariesfordistributedcomputing(Bednarand Durant 2023):
ticestoensurerobustnessandmaintainability.Theseinclude
(cid:2) coding best practices, modular design, extensive tests, and
Zarr,alibrarythatimplementsthecloud-optimized Zarr
continuous integration and deployment (CI/CD). Echopype storage format (The Net CDF NCZarr Implementation
follows the PEP8 style guidelines for Python code (PEP 8
n.d.,Zarrn.d.);
(cid:2) n.d.), enhancing readability and cleanliness, making it eas-
Xarray,alibraryformanipulatingmulti-dimensionalla-
ier for the community to understand and contribute. An
beleddata(Hoyerand Hamman 2017);and
(cid:2) automated framework using pre-commit and pre-commit.ci
Dask,alibraryforparallelcomputing(Daskn.d.).
(pre-commit.cin.d.)ensuresadherencetotheseguidelinesby
Specifically,chunkedandcompressed Zarrdatasetscanbe executingvalidationsbeforecodeadditions.
read and computed directly via Xarray,which transparently The modular design of Echopype’s package structure sup-
leverages Daskfordistributedcomputationandtaskschedul- ports easy extension for additional instrument models and
ing.Westrivetoimplement alldatainterfacing andprocess- new data processing functionalities. Robustness is ensured
ing functions in Echopype to take advantage of the compu- through extensive tests with both real instrument-generated
tational scalability offered by these libraries.We have found data files and mock data (simulated data that mimics real
that raw resolution echosounder data are often irregularly data).Thesetests,includingunitandintegrationtests,canbe
structured in time and space, and therefore require custom runlocallyduringdevelopmentorautomaticallyvia Git Hub
optimizationbeyondstock Xarrayfunctionstoparallelizeef- Actions when changes are uploaded to the repository. This
ficiently across computing agents. The combination of us- automated system also handles building and distributing the
ing Dasktodistributepre-specified(“delayed”)computation Echopypepackagetothe Python Packaging Index(Py PIn.d.)
on organized Zarr data that are loaded only when neces- and the conda-forge community channel (Conda-forge n.d.)
sary(“lazy-loaded”)hasbeenparticularlypowerful,eitherin forusewiththe Condapackagemanager.
enabling out-of-core computation of datasets that are larger To support collaborative development, engage new con-
than the immediately accessible system memory, or for dis- tributors, and ensure timely updates, the project uses pub-
tributingcomputationtoacluster(Bednarand Durant 2023). lic milestones and issue tracking through Git Hub’s project
Thelabel-awarecapabilityof Xarraysignificantlyreducesthe management tools and maintains a Development Roadmap
cognitiveloadforimplementingalgorithmsthatcomputeon pageinthedocumentation.
Downloaded
from
https://academic.oup.com/icesjms/article/81/10/1941/7815946
by
Institute
of
Hydrobiology
user
on
17
June
2026

Interoperable and scalableechosounder data processingwith Echopype 1947
Packagestructureandfunctionalities directly in fisheries and oceanographic research (Simmonds
The Echopype package is platform-independent and can be and Mac Lennan 2007, Demer et al. 2015). This procedure
| | | | | | | | | is non-trivial | and | highly | instrument-specific, | | | constituting | a |
| ---------------- | --- | --------- | -------- | ------------- | ------- | ------- | ------ | -------------- | ----- | ------ | -------------------- | ------------- | --- | ------------ | --- |
| easily installed | via | Py PI | or the | Conda package | | manager | via | | | | | | | | |
| | | | | | | | | barrier for | broad | access | and | understanding | for | echosounder | |
| the conda-forge | | community | channel. | The | package | is | hosted | | | | | | | | |
and continues to be actively developed in a Git Hub reposi- data. The calibrate subpackage provides the functional-
tory(https://github.com/OSOcean Acoustics/echopype)under ity to perform this procedure. Once physically meaningful
the open-source Apache 2.0 license. Current functionalities quantities are obtained, the previously heterogeneous data
| | | | | | | | | records from | diverse | instruments | | could | be intuitively | | under- |
| ------------------------------------------ | -------- | --- | -------- | ------ | ---------- | -------- | ------ | ------------ | ------- | ----------- | --- | -------- | -------------- | ------ | ------- |
| and usage | examples | are | detailed | in the | package | documen- | | | | | | | | | |
| | | | | | | | | stood and | used | by a wider | | range of | users | beyond | experts |
| tation (https://echopype.readthedocs.io/). | | | | | Therefore, | | rather | | | | | | | | |
thanprovidingadetailedenumerationof Echopypefunction- in acoustics. Echopype currently supports Sv computation
Downloaded from https://academic.oup.com/icesjms/article/81/10/1941/7815946 by Institute of Hydrobiology user on 17 June 2026
alities that will continue to change and expand,here we opt for both narrowband (AZFP,EK60,and EK80 “CW”mode
toprovideconceptualgroupingsoffunctionalitiesthatcanbe transmission)andbroadbanddata(EK80“FM”modetrans-
| | | | | | | | | mission). | Currently | only | band-averaged | | Sv | is implemented | |
| --- | --- | --- | --- | --- | --- | --- | --- | --------- | --------- | ---- | ------------- | --- | --- | -------------- | --- |
stackedtoformanautomateddataprocessingpipeline.Asthe
| | | | | | | | | for FM data; | broadband | | Sv calculation | | will | be added | in the |
| ------------ | ---------- | --------------- | --- | --------------- | --- | ----------- | ------ | ------------ | --------- | --- | -------------- | --- | ---- | -------- | ------ |
| foundational | data | standardization | | components | | of Echopype | | | | | | | | | |
| mature, | we plan | to redirect | our | attention | to | focus | on ex- | nearfuture. | | | | | | | |
| panding | downstream | processing | | functionalities | | and comput- | | | | | | | | | |
ingscalabilityinthenextstageofdevelopment(seedetailsin Dataconsolidationandalignment
Thecalibratedechodataareoftenthemostusefulwhenbun-
Section“Discussion”).
| | | | | | | | | dled together | with | ancillary | | information | that | is crucial | for |
| --- | --- | --- | --- | --- | --- | --- | --- | ------------- | ------------------- | --------- | --- | ----------- | ---------- | ---------- | ------ |
| | | | | | | | | acoustic | data interpretation | | and | other | quantities | that | can be |
Dataconversion
derivedfromtherawacousticdata.Geospatiallocationssuch
| The Echopype | convert | | subpackage | provides | | the function- | | | | | | | | | |
| ------------ | ------- | --- | ---------- | -------- | --- | ------------- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
aslatitude,longitude,andplatformdepthareexamplesofthe
| ality to | parse and | convert | instrument-specific | | | binary | data | | | | | | | | |
| -------- | --------- | ------- | ------------------- | --- | --- | ------ | ---- | ------------- | ----------- | --- | --- | ---------- | ------ | ---- | ------ |
| | | | | | | | | former; phase | information | | or | split-beam | angles | that | can be |
filesintoastandardizedrepresentation,the Echo Dataobject,
| | | | | | | | | computed | from | EK80 | complex | samples | are | examples | of the |
| --- | --- | --- | --- | --- | --- | --- | --- | -------- | ---- | ---- | ------- | ------- | --- | -------- | ------ |
consistingofbothdataandmetadatafollowingthe Echopype
| | | | | | | | | latter. Echopype | | provides | functionalities | | through | the | con- |
| ---------- | ------ | ------------- | --- | ---------- | --- | ---- | ------- | ---------------- | --- | -------- | --------------- | --- | ------- | --- | ---- |
| adaptation | of the | SONAR-net CDF4 | | convention | | (see | Section | | | | | | | | |
solidatesubpackagetoenhancethecoherenceandbinding
“Datastandardization”).The Echo Dataobjectcanberead-
oftheseadditionalvariableswiththecalibratedechodataat
ilyserializedintonet CDF4 or Zarrformats andalsoprovides
therawdataresolution.Additionally,thecommongridsub-
| functionalities | to | incorporate | | ancillary | information, | | such as | | | | | | | | |
| --------------- | --- | ----------- | --- | --------- | ------------ | --- | ------- | --- | --- | --- | --- | --- | --- | --- | --- |
packageprovidesfunctionalitiestobringdatafromalltrans-
geographicallocations,iftheydonotalreadyexistintheraw
| | | | | | | | | ducer channels | onto | the | same | specified | temporal | and | spatial |
| ---------- | ---------- | -------- | --- | ---- | -------- | ----- | ----- | -------------- | ---------- | --- | ---- | ---------- | -------- | ---------- | ------- |
| data files | or require | updates. | The | data | read and | write | func- | | | | | | | | |
| | | | | | | | | grid,which | is desired | for | many | downstream | | processing | rou- |
tionalityarecompatiblewithbothlocal(e.g.harddrives)and
tines,includingmachinelearningapplications(Ordoñezetal.
remotefilesystems,includingcloudobjectstorage(e.g.Ama-
2022).Onecommonsuchoperationistocomputethemean
zon Web Services S3).
volumebackscatteringstrength,or MVBS(Mac Lennanetal.
| Beyond | the conversion | | of | individual | files, | we devised | a | | | | | | | | |
| ------ | -------------- | --- | --- | ---------- | ------ | ---------- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
2002),acrosspingtimeandrange,whicharecommonlyused
| combine_echodata | | function | | that allows | combining | | mul- | | | | | | | | |
| ---------------- | --- | -------- | --- | ----------- | --------- | --- | ---- | --- | --- | --- | --- | --- | --- | --- | --- |
toreducedatavariability.
| tiple Echo Data | | objects, | each | from a | raw data | file, | into a | | | | | | | | |
| -------------- | --- | -------- | ---- | ------ | -------- | ----- | ------ | --- | --- | --- | --- | --- | --- | --- | --- |
singlecombined Echo Dataobject.Thismakesitpossibleto
Datafilteringandselection
coalescedatafromnumerousindividualrawfilesintolarger,
Datafilteringandselectionareimportantcomponentsofcom-
meaningfulentitiesdependingonthedatacollectionmission.
monechosounder data processingpipelines.Datafilteringtyp-
Forexample,thousandsofrawfilesfromafisherysurveycan
icallyincludesqualitycontrolstepsthatdetectandhandleer-
beorganizedintoonlytensof Echo Dataobjects,eachrepre-
roneousdataentriesornoisydata.Forexample,smalltimes-
sentingasinglesurveytransect.Thousandsofrawfilesfroma
| | | | | | | | | tamp reversals | occur | occasionally | | for | data from | Kongsberg | |
| --- | --- | --- | --- | --- | --- | --- | --- | -------------- | ----- | ------------ | --- | --- | --------- | --------- | --- |
long-termmooringcanbeorganizedinto Echo Dataobjects
Simradechosoundersandshouldbecorrectedorremoved;in-
onaweeklyormonthlybasis.Similartotheuseof EVfilesin
fluenceofbackgroundnoisethatisspecificforeachsystemcan
| Echoview | to group | and | index | raw data | files,such | organiza- | | | | | | | | | |
| -------- | -------- | --- | ----- | -------- | ---------- | --------- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
beestimatedandmitigated;impulsivenoisespikesfromtrans-
tionalsimplificationcandramaticallyalleviatetheburdenof
missionsofotheracousticinstruments,suchasthe ADCPsand
datawrangling,allowingresearcherstofocusontheanalysis
crosstalkfromothertransducerchannelsshouldberemoved
oflogicallygroupedechodatasets.
(e.g.De Robertisand Higginbottom 2007,Ryanetal.2015).
Atpresent,Echopypesupportsconvertingbinarydatafiles
Dataselection,ontheotherhand,typicallyinvolvesclassify-
generatedbythefollowingsystems:Kongsberg Simrad EK60,
ingandselectingpartsoftheechodatathatresultfromspecific
EK80,Kongsberg EA640,andsimilarechosounders(e.g.the
| | | | | | | | | scattering | sources. | For | example, | using | manual | or automatic | |
| --- | --- | --- | --- | --- | --- | --- | --- | ---------- | -------- | --- | -------- | ----- | ------ | ------------ | --- |
ESfamilyofechosounders),and ASLEnvironmental Sciences
procedures,anechogramcanbesegmentedintoregionscon-
Acoustic Zooplanktonand Fish Profiler(AZFP).Conversion
tainingatargetfishspeciesandregionsbelowtheseafloor(e.g.
| is also | possible | for data | from | the Nortek | Signature | | series | | | | | | | | |
| ------- | -------- | -------- | ---- | ---------- | --------- | --- | ------ | -------- | -------- | ----- | --- | -------- | ------ | --------------- | --- |
| | | | | | | | | Jech and | Michaels | 2006, | De | Robertis | et al. | 2010, Brautaset | |
ADCP,butthestructureoftheresulting Echo Dataobjectre-
etal.2020).Thesedatafilteringstepsaretypicallycomputa-
quiresfurtherchangestobefullyconsistentwiththosefrom
tionallyintensivebottlenecksinechosounder data processing
othersonarmodels.
workflows.Echopypeutilizesdistributedcomputinglibraries
| | | | | | | | | to enhance | the efficiency | | of these | functions | and | enables | out- |
| --- | --- | --- | --- | --- | --- | --- | --- | ---------- | -------------- | --- | -------- | --------- | --- | ------- | ---- |
Calibration
of-memorycomputationforprocessinglargedatasetsonlocal
Acousticdatarecordedbyechosounderinstrumentstypically computerswithlimitedresources.Currently,Echopypeoffers
requires additional unit conversion and calibration to arrive basic filtering and selection functions within its qc, clean,
atphysicallymeaningfulquantities(e.g.Sv)thatcanbeused andmasksubpackages,withongoingeffortstoexpandthese

| 1948 | | | | | | | | | | | | Leeetal. | |
| ---- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | -------- | --- |
capabilities.It is important to note that Echopype is not de- inshipechosounderdata,andcompute NASCbasedon
signed for manual echogram cleaning, as mentioned in Sec- themaskedoutputs.
tions“Introduction”and“Designphilosophy.” 5. glider_AZFP.ipynb: Process acoustic data from a
| | | | | | | glider | by incorporating | | external | position,motion,and | | | |
| --- | --- | --- | --- | --- | --- | ------ | ---------------- | --- | -------- | ------------------- | --- | --- | --- |
Otherfunctionalities
environmentaldataandidentifyzooplanktonschools.
Inadditiontotheabovefunctionalitiesthatmostlyfallunder
theumbrellaofdataengineeringtoenablebroaderandmore
| | | | | | | Each notebook | | includes | an | introductory | section | | that de- |
| -------------- | ----------------- | --- | ------------- | --- | ----------- | ------------- | ----- | -------- | --------- | ------------ | ------- | ----------- | -------- |
| flexible usage | of data, Echopype | | also includes | | subpackages | | | | | | | | |
| | | | | | | scribes the | goals | and the | workflow, | followed | | by computa- | |
thatarecollectionsofdataanalysisorutilityfunctions,such
| | | | | | | tional sections | where | code | is interwoven | | with | textual | expla- |
| --- | --- | --- | --- | --- | --- | --------------- | ----- | ---- | ------------- | --- | ---- | ------- | ------ |
asthemetricsandutilssubpackages.Weanticipatethat
| | | | | | | nations.Allnotebooksfollowthegeneral Echopypeworkflow | | | | | | | Downloaded from https://academic.oup.com/icesjms/article/81/10/1941/7815946 by Institute of Hydrobiology user on 17 June 2026 |
| --- | --- | --- | --- | --- | --- | ---------------------------------------------------- | --- | --- | --- | --- | --- | --- | ----------------------------------------------------------------------------------------------------------------------------- |
thesesubpackagegroupingswillchangeasmoredataanaly-
(Fig.1)thatstandardizesdatabeforefurthercomputations.
| sis functionalities | are added | to Echopype | | in the | future,such | | | | | | | | |
| ------------------- | --------- | ----------- | --- | ------ | ----------- | ------ | ------------ | --- | ---------------------- | --- | --- | --- | --- |
| | | | | | | Two of | the examples | | (krill_freq_diff.ipynb | | | | and |
assingletargetandgroup(swarm)detection.Atpresent,the
| | | | | | | ship_tracks.ipynb) | | | by default | involve | converting | | hun- |
| --- | --- | --- | --- | --- | --- | ------------------ | --- | --- | ---------- | ------- | ---------- | --- | ---- |
metricssubpackagecontainsfunctionstocomputeping-by-
dredsofrawdatafilesdirectlyfromthedatasourcesandcan
| ping summary | statistics | of echoes | that are | useful | for obtain- | | | | | | | | |
| ------------ | ---------- | --------- | -------- | ------ | ----------- | ----------------- | --- | ------ | ------- | ---------- | --- | ------- | ---- |
| | | | | | | be slow depending | | on the | network | condition. | | We have | pro- |
ingaquickoverviewoflargeechosoundertimeseries(Urmy
videdthecodesegmenttosubselectonlyaportionofthedata
etal.2012).Theutilssubpackagecontainsutilityfunctions
| | | | | | | for quick | testing. | For all | notebooks, | we | note | that the | same |
| --- | --- | --- | --- | --- | --- | --------- | -------- | ------- | ---------- | --- | ---- | -------- | ---- |
forlogging,maintainingdataprovenance,handlinglocaland
codecanscaledirectlytolargerdatasetswhenusedoncloud
cloudpaths,andspecifyingvariableencoding,etc.
virtualmachinesoron-premiseclusterswithmuchlargercom-
Previously,Echopypecontainedthevisualizesubpack-
putingresources.
| age to provide | simple plotting | functions. | | We have | removed | | | | | | | | |
| -------------- | --------------- | ---------- | --- | ------- | ------- | --- | --- | --- | --- | --- | --- | --- | --- |
Belowwehighlightkeyelementsacrossthenotebooksthat
| this subpackage | and expanded | our | documentation | | page to | | | | | | | | |
| --------------- | ------------ | --- | ------------- | --- | ------- | --- | --- | --- | --- | --- | --- | --- | --- |
demonstratethepowerof Echopypeasanintegratedcompo-
demonstratehowtousenative Xarrayfunctionalitiestogen-
nentoftheopen-sourcescientific Pythonsoftwareecosystem:
eratethesameplots.Forinteractivevisualization,wehavecre-
| ated and | continue to develop | a separate | | software | package, | | | | | | | | |
| -------- | ------------------- | ---------- | --- | -------- | -------- | --- | --- | --- | --- | --- | --- | --- | --- |
(cid:2)
Echoshader, to provide configurable, interactive “widgets.” Alloperationsarecarriedoutwithinasinglecomputing
Multiplewidgetscanbecombinedinadashboardtoexplore environment,inwhich Echopypefunctionalitiesareused
differentfacetsofthesamedatasetsinteractively(Echoshader togetherwithfunctionsfromcorescientific Pythonsoft-
n.d.).Notethat Echoshaderdoesnotprovidemanualannota- warepackages,suchas Num Py,Pandas,Matplotlib,etc.,
tionoreditingcapabilitieslike GUI-basedsoftwarepackages. as well as custom routines such as those implemented
| | | | | | | in echopy | (open-ocean-sounding | | | 2021). | | Treating | these |
| --- | --- | --- | --- | --- | --- | --------- | -------------------- | --- | --- | ------ | --- | -------- | ----- |
notebooksasblueprints,userscaneasilymodifythecode
| Use case | examples | | | | | | | | | | | | |
| -------- | -------- | --- | --- | --- | --- | ------- | ------ | ---- | ---------- | --------- | --- | ------------ | --- |
| | | | | | | and add | custom | data | processing | functions | | to construct | |
Along with the main code repository, we provide a theirownworkflow.
(cid:2)
companion repository, echopype-examples (https: Theflexibilityof Echopypetodirectlyinterfacewithlo-
//echopype-examples.readthedocs.io/), to demonstrate the cal or cloud file systems and object stores makes the
use of Echopype via executable Jupyter Notebooks. The workflows in these notebooks highly adaptable proto-
notebooks are not exhaustive of all Echopype functions and typesthatcanberunasscriptsforresearchuseaswell
details, as they are provided in the package documentation asmassproductionofanalysis-readydataproducts.
(cid:2)
andwillcontinuetoevolveasthepackagedevelops.Weplan Researchers can easily inspect and plot the data being
toupdatethesenotebooksregularly,addnewexamples,and processedatanystageoftheworkflowwithinthenote-
acceptusersubmissions. books.Datageneratedfrom Echopypeisalsohighlyin-
This repository currently contains five notebooks that teroperable with other oceanographic datasets,such as
demonstrate Echopypefunctionalitiesusingechosounderdata thepyrometermeasurementsshownintheeclipsenote-
| from a ship,a | mooring,and | a glider.The | | topics | of the note- | book. | | | | | | | |
| ------------- | ----------- | ------------ | --- | ------ | ------------ | ----- | --- | --- | --- | --- | --- | --- | --- |
(cid:2)
| booksare: | | | | | | Duetotheopen-sourcenatureof Echopype,userscanset | | | | | | | |
| --------- | --- | --- | --- | --- | --- | ----------------------------------------------- | --- | --- | --- | --- | --- | --- | --- |
breakpointswithinthe Echopypecodebasetoeasilylook
1. OOI_eclipse.ipynb: Pair acoustic data from an “underthehood”andvalidatethecomputationalimple-
upward-lookingechosounderandshortwaveirradiance mentations inan Integrated Development Environment
measuredbyapyrometeronasurfacemooringtoob- (IDE)compatiblewith Python.
(cid:2)
servethemovementresponseofzooplanktontoasolar Echopype’s ability to aggregate numerous instrument-
eclipse. generated raw data files of large volumes into a single
2. ship_tracks.ipynb:Subselectsectionsofechodata orahandfulofcombinedentitieslessensthedatawran-
based on ship GPS data embedded in the echosounder gling complexity and cognitive overhead in analyzing
rawfilestodemonstratethepoweroflabel-awaredata largedatasets.Theseentitiescanbeflexiblychosenbased
processingbasedonstandardizednet CDFdatamodel. onapplicationcontext,suchasweeklyormonthlyaggre-
3. krill_freq_diff.ipynb: Perform frequency- gatesformooringdata,orsingle-transectaggregatesfor
| differencing | analysis | to identify | fluid-like | | zooplankton | shipdata. | | | | | | | |
| ------------ | -------- | ----------- | ---------- | --- | ----------- | --------- | --- | --- | --- | --- | --- | --- | --- |
(cid:2)
scatterers (likely krill) in ship echosounder data, and The core Echopype functions shown in the notebooks
computenauticalacousticscatteringcoefficient(NASC) are scalable,both for performing out-of-core computa-
basedontheclassification. tionswhentheaccessiblememoryislimited,andfordis-
4. hake_mask.ipynb: Incorporate an externally gener- tributing computations across larger memory and pro-
atedmaskthatidentifiestheoccurrenceof Pacifichake cessingresources.

Interoperable and scalableechosounder data processingwith Echopype 1949
Discussion generate a cloud-hosted Zarr data lake (Wall et al. 2023),
which feeds into a web visualization app (Wall et al.2020).
In this paper, we present Echopype, an open-source Python
These examples show the growing influence of Echopype in
software package designed for interoperable and scalable
expanding the use of echosounder data beyond the fisheries
echosounder data processing for biological information.
acoustics community to reach a broader base of potential
Echopype draws insights from decades of echosounder soft-
users.
ware development while leveraging recent advancements in
Echopype is well positioned to expand its functionalities
cloud and distributed computing from the wider geoscience
underthegoalsofinteroperabilityandscalability.Themodu-
domain.Throughaconsistentprogrammaticinterfaceacross
larizedpackagestructureprovidesaconceptuallyunifiedim-
datastorageandcomputinglocations(localorcloud)andin-
plementationframeworkfor:(1)addingsupport formoreraw
strumentsources,Echopypeeasilyintegrateswithtoolsinthe
instrument-generateddataformatsfromotherechosounders,
expansivescientific Pythonecosystemfororganizingandan-
and (2) incorporating additional data processing and analy-
alyzingechosounderdata.Byfirstconvertingandstandardiz-
sis methods downstream of the standardized data. With the
ingdataintoformatsthatareconducive todistributed com-
maturationofthefoundationaldatastandardizationcompo-
putation before downstream processing, Echopype provides
nentsin Echopype,ourgoalsinthenextstageofdevelopment
aclearlydefinedpathforextendingcomputationalefficiency
include: further optimize distributed computing efficiency of
andversatilityinfutureworkflows.
existingfunctions;incorporateadditionalcommondatapro-
Echopype is being adopted rapidly by the fisheries acous-
cessing methods (e.g. single target detection, bottom detec-
ticsandthewideroceanographycommunities.Sincethepack-
tion,etc.);addsupport fordatafromotherechosoundermod-
age’sfirstreleaseinearly 2019,weregularlyreceivedbugre-
els (e.g.Simrad EK500 and multi-beam data); improve data
portsandfeaturerequestsbothinour Git Hubrepositoryand
provenancetracking;andenhanceadherencetoexistingand
throughprivateemails.Themajorityofbugreportsweredata
emergingcommunityconventions.Theseareaccompaniedby
parsing issues from the evolving data format of the Kongs-
the continuing development of a set of data processing level
berg Simrad EK80 echosounder. The majority of feature re-
definitionsforechosounderdata(Echolevelsn.d.),whichwill
questsareforaddingpopularechosounderdataanalysisfunc-
facilitate data understanding and provenance tracking. Cur-
tions for specific application scenarios (e.g. tracking single
rently, many Echopype functions generate data provenance
scatterers over multiple pings,delineating the outlines of an
and processing level information as variables or attributes
animalaggregation)andforexpandingsupport fordatacol-
within the datasets. These are prototypes we plan to refine
lected by other echosounder instruments. Although there is
inthefuture.
currently no single comprehensive method or platform for
As with all open-source software,the future development
tracking usage statistics for Python packages, at the time of
of Echopype relies heavily on the engagement and feedback
writing, Py PI Stats (https://pypistats.org/packages/echopype)
from the diverse echosounder user community,including re-
reports regular daily download counts ranging from single
searchers,datamanagers,andengineers,eachwiththeirspe-
digits to lower tens. A more detailed report via the pyp-
cific use cases and challenges. Through the publicly hosted
info package (pypinfo n.d.) shows that over the last year,
code repository, clear contribution guidelines, and a modu-
Echopype has been downloaded in 10 countries (ordered by
larpackagestructure,Echopypelaysasolidfoundationfora
decreasingdownloadcounts:USA,Denmark,Norway,Singa-
collaborative,community-drivenapproachtosoftwaredevel-
pore,Netherlands,France,Sweden,Australia,Great Britain,
opment centered around echosounder data.We plan to con-
and Canada), on Linux, Windows, and Mac OS operating
tinuedeveloping Echopypebyactivelysupporting,collaborat-
systems, and on different cloud providers (e.g. Azure, Ama-
ing with, and receiving contributions from the echosounder
zon). We also observe a trend of increasing adoption of
user community. We envision that the growth of this pack- Echopype:forexample,downloadson Windowsand Mac OS
agewillcatalyzetheintegration ofinformationderivedfrom
operating systems (to avoid inflation due to automatic test-
ingserviceson Linux)haveincreasedfrom<100 downloads echosounderdataintoregionalandglobaloceanobservation
strategies.
in 2020 to over 500 downloads in 2024, with a rapid in-
crease over the last two years. We expect these numbers to
belargersincepypinfoincludesonlydownloadsfrom Py PI,
Acknowledgements
but Echopypecanalsobedownloadedthroughconda.Inad-
dition, the Echopype Git Hub repository has received 72 is- Wethankallpreviousandcurrentcontributorsto Echopype,
sue submissions, 50 pull request submissions, and 87 stars including those whose contributions do not include code.In
from contributors in both academic institutions and govern- particular,wethank Dave Billennessforprovidingthe AZFP
mentagenciesoutsidethecoredevelopmentteam.Whilethese Matlab Toolbox as reference for developing support for the
numbers are not particularly high, they are consistent with AZFP echosounder, Rick Towler for providing low-level file
the moderate size of the global scientific echosounder user parsing routines for Simrad EK60 and EK80 echosounders,
community. and Alejandro Ariza for developing Num Py implementation
In addition to individual users, the US OOI cyberinfras- ofacousticanalysisfunctionsvia Echopy,whichwereferenced
tructureserviceshaveincorporated Echopypeintotheirpro- for several Echopype functions. We also thank Imran Ma-
cessing pipeline for serving bio-acoustic sonar data products jeed,Kavin Nguyen,Praneeth Ratna,and Brandon Reyesfor
(OOI-CGSN n.d.).These data products were previously un- their code contribution, Brandyn Lucca for providing com-
availableduetothecomplexitiesassociatedwiththespecial- mentsonthemanuscript,andsupportfromthe Universityof
izedechosounderrawdataformats andcalibrationneeds.The Washington Scientific Software Engineering Centerfundedby
NOAANCEIWater Column Sonar Dataarchivehasalsoin- Schmidt Futures as part of the Virtual Institute for Scientific
corporated Echopype into the backbone of their pipeline to Software.
Downloaded
from
https://academic.oup.com/icesjms/article/81/10/1941/7815946
by
Institute
of
Hydrobiology
user
on
17
June
2026

| 1950 | | | | | | | | | | | | | Leeetal. |
| ---- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | -------- |
Author contributions Dask: Scalable analytics in Python. n.d. https://dask.org/ (8 August
2024,datelastaccessed).
| W.-J.L. | initiated | and continue | | to lead | the | package | devel- | | | | | | |
| ------- | --------- | ------------ | --- | ------- | --- | ------- | ------ | --- | --- | --- | --- | --- | --- |
De Robertis A,Higginbottom I.Apost-processingtechniquetoestimate
| opment. | W.-J.L. | conceptualized | | the manuscript. | | W.-J.L. | and | | | | | | |
| ------- | ------- | -------------- | --- | --------------- | --- | ------- | --- | --- | --- | --- | --- | --- | --- |
thesignal-to-noiseratioandremoveechosounderbackgroundnoise.
| E.M.wrote | the manuscript.C.T.contributed | | | | | significantly | to | | | | | | |
| --------- | ------------------------------ | --- | --- | --- | --- | ------------- | --- | --- | --- | --- | --- | --- | --- |
ICESJMar Sci 2007;64:1282–91.https://doi.org/10.1093/icesjms/
| manuscript | revisions | and | preparing | the | example | notebooks. | | fsm 112 | | | | | |
| ---------- | --------- | --- | --------- | --- | ------- | ---------- | --- | ------ | --- | --- | --- | --- | --- |
L.S.and V.S.providedimportantsuggestions.Allauthorscon- De Robertis A, Mc Kelvey DR, Ressler PH.Developmentandapplica-
tributedsignificantlytothedesign,code,testinganddocumen- tionofanempiricalmultifrequencymethodforbackscatterclassifi-
tation of the package.All authors revised and approved the cation.Can JFish Aquat Sci 2010;67:1459–74.https://doi.org/10.1
| manuscript. | | | | | | | | 139/F10-075 | | | | | |
| ----------- | --- | --- | --- | --- | --- | --- | --- | -------------------- | --- | ------------------------------- | --- | --- | --- |
| | | | | | | | | Demer DA, Andersen LN, | | Bassett Cetal.2016 USA-Norway EK80 | | | |
Conflictofinterest:Theauthorshavenoconflictofinterestto Downloaded from https://academic.oup.com/icesjms/article/81/10/1941/7815946 by Institute of Hydrobiology user on 17 June 2026
Workshop Report:Evaluationofa Wideband Echosounderfor Fish-
declare.
eriesand Marine Ecosystem Science.In:ICESCooperative Research
Report No 336.2017,79.
Funding Demer DA, Berger L, Bernasconi Metal.Calibrationofacousticin-
struments.In:ICESCooperative Research Report No.326.2015,
| This work | was | supported | by | the | US National | Science | | 136. | | | | | |
| --------- | --- | --------- | --- | --- | ----------- | ------- | --- | ---- | --- | --- | --- | --- | --- |
Foundation (NSF) Award No. 1849930, National Oceanic Eaton B, Gregory J, Drach Betal.Representationsofcollectionsof
and Atmospheric Administration (NOAA) Award No. features in data variables.n.d.http://cfconventions.org/Data/cf-co
NA21 OAR0110201, NA20 OAR0110429, the Coopera- nventions/cf-conventions-1.8/cf-conventions.html#representations
-features(8 August 2024,datelastaccessed).
| tive Institute | for | Climate, | Ocean, | | and Ecosystem | | Stud- | | | | | | |
| -------------- | --- | -------- | ------ | ----------- | ------------- | --------- | ----- | ----------------------- | --- | -------- | ------ | --------------------- | ---- |
| | | | | | | | | Echolevels: Discussions | | on water | column | sonar data processing | lev- |
| ies (CICOES) | | under | NOAA | Cooperative | | Agreement | | | | | | | |
els.n.d.https://github.com/OSOcean Acoustics/echolevels(8 August
| NA20 OAR4320271, | | and | National | Aeronautics | | and | Space | | | | | | |
| --------------- | --- | --- | -------- | ----------- | --- | --- | ----- | --- | --- | --- | --- | --- | --- |
2024,datelastaccessed).
Administration(NASA)Award No.17-ACCESS17-0003.
| | | | | | | | | Echoshader: Interactive | | visualization | of ocean | sonar data.n.d.https: | |
| --- | --- | --- | --- | --- | --- | --- | --- | ---------------------------------------- | --- | ------------- | -------- | --------------------- | --------- |
| | | | | | | | | //github.com/OSOcean Acoustics/echoshader | | | | (8 August | 2024,date |
lastaccessed).
Data availability
| | | | | | | | | Echoview: Hydroacoustic | | data | processing.n.d.https://echoview.com/ | | |
| --- | --- | --- | --- | --- | --- | --- | --- | ----------------------- | --- | ---- | ------------------------------------ | --- | --- |
The data used in the example Jupyter notebooks in this ar- (8 August 2024,datelastaccessed).
ticle are available at the following locations: The mooring Harrison L-MK, Cox MJ, Skaret Getal.The Rpackage EchoviewR
datawerecollectedbythe USOcean Observatories Initiative for automated processing of active acoustic data using Echoview.
(OOI) Regional Cabled Array and are available in the OOI Front Mar Sci 2015;2.https://doi.org/10.3389/fmars.2015.00015
| | | | | | | | | Hassell D, Gregory | J, | Blower | J et al.A | data model of | the Climate |
| --- | --- | --- | --- | --- | --- | --- | --- | ------------------ | --- | ------ | --------- | ------------- | ----------- |
Raw Data Archive(an HTTPserver)athttps://rawdata.ocea
and Forecastmetadataconventions(CF-1.6)withasoftwareimple-
nobservatories.org/files/.Theshipdatawerecollectedaspart
mentation(cf-pythonv 2.1).Geosci Model Dev 2017;10:4619–46.
| of the 2017 | Joint | U.S. | and Canada | Pacific | Hake | Integrated | | | | | | | |
| ----------- | ----- | ---- | ---------- | ------- | ---- | ---------- | --- | --- | --- | --- | --- | --- | --- |
https://doi.org/10.5194/gmd-10-4619-2017
Acousticand Trawl Survey(Northwest Fisheries Science Cen-
| | | | | | | | | Hoyer S, Hamman | J. | Xarray: | N-D labeled | arrays and | datasets in |
| --- | --- | --- | --- | --- | --- | --- | --- | --------------- | --- | ------- | ----------- | ---------- | ----------- |
ter,Fishery Resource Analysisand Monitoring Division 2019)
Python.JOpen Res Softw 2017;5:10.https://doi.org/10.5334/jors
| and are | available | in the | NOAA | Water-Column | | Sonar | Data | .148 | | | | | |
| ------- | --------- | ------ | ---- | ------------ | --- | ----- | ---- | ---- | --- | --- | --- | --- | --- |
Archive AWS S3 bucket (a cloud object container) at http ICESWGFASTTopic Group(TG-Ac Meta).SISP4-Ametadatacon-
s://registry.opendata.aws/ncei-wcsd-archive/.The glider data vention for processed acoustic data from active acoustic systems.
were provided by Delphine Mossman from the Department Version 10.Seriesof ICESSurvey Protocols.2016,48.
of Marine and Coastal Sciences at Rutgers University by ICES Working Group on Global Acoustic Interoperable Network
(GAIN).2024.https://github.com/ices-eg/wk_WKGAIN(8 August
permissionandareavailableintheechopype-examplerepos-
2024,datelastaccessed).
itory at https://github.com/OSOcean Acoustics/echopype-exa
| | | | | | | | | Jech JM, Michaels WL.Amultifrequencymethodtoclassifyandevalu- | | | | | |
| --- | --- | --- | --- | --- | --- | --- | --- | ----------------------------------------------------------- | --- | --- | --- | --- | --- |
mples.
atefisheriesacousticsdata.Can JFish Aquat Sci 2006;63:2225–35.
https://doi.org/10.1139/f 06-126
References Jupyter:Freesoftware,openstandards,andwebservicesforinteractive
computingacrossallprogramminglanguages.n.d.https://jupyter.or
Bednar JA,Durant M.The Pandatascalableopen-sourceanalysisstack. g/(8 August 2024,datelastaccessed).
Proceedingsofthe 2023 Scientific Computingin Python Conference Korneliussen R, Eliassen I, Heggelund Y. Large Scale Survey Sys-
(Sci Py 2023) 2023;85–92.https://doi.org/10.25080/gerudo-f 2 bc 6 f tem(LSSS)becomesopensourcefrom January 2025.In:The 2024
59-00 b ICESWorking Groupon Fisheries Acoustics,Scienceand Technol-
ogy(WGFAST)meeting.Brest,France,2024.
| Brautaset O, | Waldeland AU, | | Johnsen Eetal.Acousticclassificationin | | | | | | | | | | |
| ----------- | ------------ | --- | ------------------------------------- | --- | --- | --- | --- | -------------- | ----- | --------------------------------------- | --- | --- | --- |
| | | | | | | | | Korneliussen R, | Ona E, | Eliassen Ietal.Thelargescalesurveysystem | | | |
multifrequencyechosounderdatausingdeepconvolutionalneural
| | | | | | | | | - LSSS. In: | Proceedings | of the | 29 th Scandinavian | Symposium | on |
| --- | --- | --- | --- | --- | --- | --- | --- | ----------- | ----------- | ------ | ----------------- | --------- | --- |
networks.ICESJMar Sci 2020;77:1391–400.https://doi.org/10.1
Physical Acoustics.Ustaoset,Norway,2006.https://www.semantic
093/icesjms/fsz 235
scholar.org/paper/THE-LARGE-SCALE-SURVEY-SYSTEM-LSSS
| CF Metadata | Conventions. | | n.d. http://cfconventions.org/ | | | (8 | August | | | | | | |
| ----------- | ------------ | --- | ------------------------------ | --- | --- | --- | ------ | ------------------------------------------------------ | --- | --- | --- | --- | --- |
| | | | | | | | | -Korneliussen/d 72 bd 4965 a 4 e 28347833278 ce 3 a 419 dacfc 976 a 3 | | | | | (8 |
2024,datelastaccessed).
August 2024,datelastaccessed).
| Chu D, Parker-Stetter S, | | Hufnagle LCetal.2018 Unmanned Surface | | | | | | | | | | | |
| ---------------------- | --- | ---------------------------------- | --- | --- | --- | --- | --- | ----------------- | --- | ----------- | ------- | ------ | ------- |
| | | | | | | | | Kunnath H, Kloser | R, | Ryan T.IMOS | SOOP-BA | Net CDF | conven- |
Vehicle(Saildrone)acousticsurveyoffthewestcoastsofthe United
tions Version 2.2.IMOS:CSIRO,2018,42.
Statesand Canada.OCEANS2019 MTS/IEEESeattle.IEEE,2019.
| | | | | | | | | Ladroit Y, Escobar-Flores | | PC, | Schimel ACG | et al. ESP3: | an open- |
| ------- | ------ | ----------------------------------------- | --- | --- | --- | --- | --- | ------------------------- | --- | ---------------- | ----------- | ----------------- | -------- |
| Colbo K, | Ross T, | Brown Cetal.Areviewofoceanographicapplica- | | | | | | | | | | | |
| | | | | | | | | source software | for | the quantitative | processing | of hydro-acoustic | |
tionsofwatercolumndatafrommultibeamechosounders.Estuar
| | | | | | | | | data. Software X | 2020;12:100581. | | https://doi.org/10.1016/j.softx. | | |
| --- | --- | --- | --- | --- | --- | --- | --- | --------------- | --------------- | --- | -------------------------------- | --- | --- |
Coast Shelf Sci 2014;145:41–56.https://doi.org/10.1016/j.ecss.201
2020.100581
4.04.002
Macaulay G,Peña H.The SONAR-net CDF4 conventionforsonardata,
Conda-forge:communitydrivenpackagingforconda.n.d.https://cond
Version 1.0.ICESCooperative Research Report No.341.2018,33.
a-forge.org/(8 August 2024,datelastaccessed).

Interoperable and scalableechosounder data processingwith Echopype 1951
Mac Lennan D, Fernandes PG, Dalen J. A consistent approach to Snowden D, Tsontos VM, Handegard NOetal.Datainteroperability
definitions and symbols in fisheries acoustics. ICES J Mar Sci betweenelementsofthe Global Ocean Observing System.Front Mar
2002;59:365–9.https://doi.org/10.1006/jmsc.2001.1158 Sci 2019;6.https://doi.org/10.3389/fmars.2019.00442
McQuinn IH, Reid D.Descriptionofthe ICESHACStandard Data Ex- Stanton TK.30 yearsofadvancesinactivebioacoustics:apersonalper-
change Format,version 1.60.ICESCooperative Researchreport No. spective.Methods Oceanogr 2012;1–2:49–77.
278.2005,88. Suberg L, Wynn RB, Kooij JVDetal.Assessingthepotentialofau-
Medwin H, Clay CS.Fundamentalsof Acoustical Oceanography.Cam- tonomoussubmarineglidersforecosystemmonitoringacrossmul-
bridge,Massachusetts,USA:Academic Press,1998,712. tipletrophiclevels(planktontocetaceans)andpollutantsinshallow
Moline MA, Benoit-Bird K, O’Gorman Detal.Integrationofscientific shelfseas.Methods Oceanogr 2014;10:70–89.https://doi.org/10.1
echosounderswithanadaptableautonomousvehicletoextendour 016/j.mio.2014.06.002
understanding of animals from the surface to the bathypelagic. J Tanhua T, Pouliquen S, Hausman Jetal.Ocean FAIRData Services.
Atmos Oceanic Technol 2015;32:2173–86.https://doi.org/10.1175/ Front Mar Sci 2019;6.https://doi.org/10.3389/fmars.2019.00440
JTECH-D-15-0035.1 The Net CDF NCZarr Implementation.n.d.https://docs.unidata.ucar.
Northwest Fisheries Science Center, Fishery Resource Analysis and edu/netcdf-c/current/md__media_psf_Home_Desktop_netcdf_rel
Monitoring Division. The 2017 Joint U.S. and Canada Pacific eases_v 4_9_2_release_netcdf_c_docs_nczarr.html (8 August 2024,
Hake Integrated Acousticandtrawl Survey:cruisereport SH-17-07. datelastaccessed).
2019. https://repository.library.noaa.gov/view/noaa/19942 (8 Au- Trenkel VM, Berger L, Bourguignon S et al. Overview of recent
gust 2024,datelastaccessed). progressinfisheriesacousticsmadeby Ifremerwithexamplesfrom
OOI-CGSNtoolsfordataanalysis.n.d.https://github.com/oceanobse the Bayof Biscay.Aquatic Living Resources 2009;22:433–45.https:
rvatories/ooicgsn-data-tools(8 August 2024,datelastaccessed). //doi.org/10.1051/alr/2009027
open-ocean-sounding. Echopy. n.d. https://github.com/open-ocean-so Unidata.Network Common Data Form(Net CDF).n.d.https://www.un
unding/echopy(8 August 2024,datelastaccessed). idata.ucar.edu/software/netcdf/(8 August 2024,datelastaccessed).
Ordoñez A, Utseth I, Brautaset O et al.Evaluation of echosounder Urmy SS, Horne JK, Barbee DH. Measuring the vertical distribu-
datapreparationstrategiesformodernmachinelearningmodels. tionalvariabilityofpelagicfaunain Monterey Bay.ICESJMar Sci
Fish Res 2022;254:106411.https://doi.org/10.1016/j.fishres.2022. 2012;69:184–96.https://doi.org/10.1093/icesjms/fsr 205
106411 Vance TC, Wengren M, Burger Eetal.Fromtheoceanstothecloud:
PEP8:Style Guidefor Python Code.n.d.https://peps.python.org/pep- opportunities and challenges for data, models, computation and
0008/(8 August 2024,datelastaccessed). workflows.Front Mar Sci 2019;6.https://doi.org/10.3389/fmars.20
Perrot Y, Brehmer P, Habasque J et al. Matecho: an open- 19.00211
source tool for processing fisheries acoustics data. Acoustics Wall C, Klucik R, Slater C et al. Towards a cloud optimized data
Australia 2018;46:241–8.https://doi.org/10.1007/s 40857-018-013 lake for archived water column sonar data. J Acoust Soc Am
5-x 2023;153:A63.https://doi.org/10.1121/10.0018170
pre-commit.ci.n.d.https://pre-commit.ci/(8 August 2024,datelastac- Wall C, Slater C, Klucik Retal.Echo Fish-Visualizing Water Column
cessed). Sonar Data.The 2020 Ocean Sciences Meeting.San Diego,Califor-
Py PI:The Python Package Index.n.d.https://pypi.org/(8 August 2024, nia,USA,2020.https://agu.confex.com/agu/osm 20/meetingapp.cgi/
datelastaccessed). Paper/652191.
pypinfo:Asimple CLItoaccess Py PIdownloadstatisticsvia Google’s Wall CC, Jech JM, Mc Lean SJ. Increasing the accessibility of
Big Query. n.d. https://pypi.org/project/pypinfo/ (8 August 2024, acoustic data through global access and imagery.ICES J Mar Sci
datelastaccessed). 2016;73:2093–103.https://doi.org/10.1093/icesjms/fsw 014
Ryan TE, Downie RA, Kloser RJ et al.Reducing bias due to noise Wall CC, Towler R, Anderson C et al.PyEcholab: an open-source,
andattenuationinopen-oceanechointegrationdata.ICESJMar python-basedtoolkittoanalyzewater-columnechosounderdata.J
Sci 2015;72:2482–93.https://doi.org/10.1093/icesjms/fsv 121 Acoust Soc Am 2018;144:1778.https://doi.org/10.1121/1.5067860
Simmonds J, Mac Lennan D. Fisheries Acoustics: Theory and Prac- Zarr:Animplementationofchunked,compressed,N-dimensionalar-
tice,2 ndedn.Hoboken,New Jersey,USA:Wiley-Blackwell,2007, rays for Python. n.d. https://zarr.readthedocs.io (8 August 2024,
1–25. datelastaccessed).
Handling Editor:Richard O’Driscoll
©The Author(s)2024.Publishedby Oxford University Pressonbehalfof International Councilforthe Explorationofthe Sea.Thisisan Open Accessarticledistributedunderthetermsofthe
Creative Commons Attribution License(https://creativecommons.org/licenses/by/4.0/),whichpermitsunrestrictedreuse,distribution,andreproductioninanymedium,providedtheoriginalwork
isproperlycited.
Downloaded
from
https://academic.oup.com/icesjms/article/81/10/1941/7815946
by
Institute
of
Hydrobiology
user
on
17
June
2026
