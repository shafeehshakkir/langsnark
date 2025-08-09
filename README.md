<img width="3188" height="1202" alt="frame (3)" src="https://github.com/user-attachments/assets/517ad8e9-ad22-457d-9538-a9e62d137cd7" />


# [Project Name] 🎯


## Basic Details
### Team Name: [Name]


### Team Members
- Team Lead: shafeeh bin shakkir SCMS SCHOOL OF ENGINEERING AND TECHNOLOGY

### Project Description
A Raspberry Pi-powered rap generator that scans nearby Wi-Fi networks, then drops a custom diss track targeting their SSIDs

### The Problem (that doesn't exist)
well some people around us have really creative wifi names, come on its time we apprecite their efforts rt?

### The Solution (that nobody asked for)
well one way to solve this issue in a creative is ig to turn it into a rap song including the SSID, haha creative rt?

## Technical Details
### Technologies/Components Used
For Software:

Languages: Python 3.11 (main code), Bash (for Wi-Fi scanning)

Frameworks: LangGraph (for flow orchestration)

Libraries:

  google-generativeai (Gemini 1.5 Flash API)

  python-dotenv (environment variables)

  subprocess + nmcli + iw (network scanning)

  espeak (offline TTS)

  ffmpeg / aplay (audio playback)

  Tools: Raspberry Pi OS terminal, .env for API keys

For Hardware:

Main component: Raspberry Pi 3 (2.4 GHz Wi-Fi)

Specifications: Quad-core 1.2GHz CPU, 1GB RAM, onboard Wi-Fi

Tools required:

Power supply for Pi

MicroSD card (OS + code)

External speakers or 3.5mm audio output

Internet connection for AI requests

### Implementation
For Software:
--> Clone repo
git clone (https://github.com/shafeehshakkir/langsnark/)

--> Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

--> Install dependencies
pip install -r requirements.txt

--> Install system tools
sudo apt update
sudo apt install -y espeak ffmpeg nmcli iw


# Run
python wifi_rapgraph.py
#.env should have gemini api

### Project Documentation
For Software:

# Screenshots (Add at least 3)
<img width="1919" height="878" alt="image" src="https://github.com/user-attachments/assets/0c35bb73-569a-4105-a7af-a62a59eda7e4" />
this image shows how whole thing is implemented 

<img width="1275" height="894" alt="image" src="https://github.com/user-attachments/assets/a96cc6af-77b9-4aa4-81be-30fa42a39870" />
this image shows the telegram bot which sends you the rap lyrics to your inbox


![Screenshot3](Add screenshot 3 here with proper name)
*Add caption explaining what this shows*

# Diagrams
![Workflow](Add your workflow/architecture diagram here)
*Add caption explaining your workflow*

For Hardware:

# Schematic & Circuit
![Circuit](Add your circuit diagram here)
*Add caption explaining connections*

![Schematic](Add your schematic diagram here)
*Add caption explaining the schematic*

# Build Photos
![WhatsApp Image 2025-08-09 at 05 22 25_4828ac8b](https://github.com/user-attachments/assets/31536614-e16b-4cd8-9322-b70fd93fbd40)


### Project Demo
# Video
https://drive.google.com/file/d/1tBpVOgo6bSPbqfHOn0iouMwVzzdoQ_5Q/view?usp=drive_link
working on the terminal


# Additional Demos
[Add any extra demo materials/links]


---
Made with ❤️ at TinkerHub Useless Projects 

![Static Badge](https://img.shields.io/badge/TinkerHub-24?color=%23000000&link=https%3A%2F%2Fwww.tinkerhub.org%2F)
![Static Badge](https://img.shields.io/badge/UselessProjects--25-25?link=https%3A%2F%2Fwww.tinkerhub.org%2Fevents%2FQ2Q1TQKX6Q%2FUseless%2520Projects)




