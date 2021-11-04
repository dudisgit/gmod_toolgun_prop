## Description
This code is for a gmod toolgun prop
![A gmod toolgun prop](https://i.imgur.com/dVuvmbS.jpeg)

## Installation

To install all the required libraries run the following in the repositories root

# Windows
```
python -m pip install -r requirements.txt
```
# Linux
```
sudo python3 -m pip install -r requirements.txt
```

## Tool creation guide

# Required tool options:
    name - The name dispalyed on the tool

# Optional tool options:
    sounds - A list of sound filenames that this tool plays
    sound_order - The oreder in which the sound is played (default is random)
        can be 'random' or 'selective'
    sound_overlap - Plays sounds over each other when the tool is fired (default is on)

    descriptions - A list of tool descriptions to display on the screen after each fire is triggered
        This will by cycled through and looped, put null if u want to have no description
    
    background - The background filename to display behind the toolgun text, image must be 240x320
    
    hold - If this tool can have its trigger held down to perform continues actions
    sound_replay - A replay timeout that after the set number of seconds will replay the sound
        Only works when 'hold' is enabled
    
    light - If the light at the end of the toolgun should light up when this tool is fired (default is true)
    motor - If the motor should spin when this tool is fired (default is true)

# Example of all:
{
    "name": "Paint",
    "descriptions": [null, "Paint some more stuff"]
    "sounds": ["sprayer.wav"],
    "sound_order": "selective",
    "sound_replay": 0.075,
    "sound_overlap": false,
    "background": "background_fix.png"
    "hold": true,
    "motor": false,
    "light": true
}