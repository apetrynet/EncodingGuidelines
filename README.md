# ORI Video Encoding recommendations.

This repository contains a variety of test suites to help pick encoding profiles suitable for VFX/Animation media reviews.
We are trying to develop best practices, so we will suggest a good starting point, but there isn't a right answer for all cases. We also try to explain what the encoding parameters do, and in what situations you might want to choose different parameters.
This is not the site for general encoding, although you may find answers here, we will likely opt for a simple one-size fits all solution over file-size efficiency.
We welcome suggestions and improvements.

This work is being done as part of the [ASWF Open Review Initiative](https://openreviewinitiative.org/). We are grateful for the ASWF for creating the collaborative cross company environment that allows such projects to exist.

The main wiki page for this for now is [here](https://wiki.aswf.io/pages/viewpage.action?pageId=16031068)

1. [Acknowledgements](#Acknowledgements)
2. [Encoding Cheat Sheet](docs/Index.md)
3. [Encoding Overview](docs/Encoding.md#Encoding-Overview)
4. [Color space conversion](docs/ColorPreservation.md#Color-space-conversion)
5. [Media Encoding with ffmpeg](docs/ColorPreservation.md#encodestart)
	1. [RGB to YCrCb Conversion](docs/ColorPreservation.md#yuv)
	2. [TV vs. Full range.](#tvfull)
	3. [RGB encode](#rgbencode)
6. [Encoding](#encode)
	1. [h264](#h264)
	2. [Prores](#prores)
7. [Metadata NCLC/NCLX](#nclc)
	1. [Gamut - colorprimaries](#gamut)
	2. [Color Range](#range)
8. [Web Review](#webreview)
