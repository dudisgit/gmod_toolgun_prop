import argparse
import json
import logging
import time
import simpleaudio
import random
from PIL import Image, ImageFont, ImageDraw
import os

from simpleaudio.shiny import play_buffer

import hardware

def content_relative(filename:str) -> str:
    """ Returns a full path from a relative filename within the content folder
    
    Args:
        filename: The name of the file within the content folder
    Returns:
        str: The full path the file within the content folder
    """
    current_dir = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(current_dir, "content", filename)

class Tool:
    """
      Represents a single tool for the toolgun
    """
    YELLOW_FADE_TIME = 0.5

    def __init__(self, app, config:dict) -> None:
        """ Creates an instance of Tool
        
        Args:
            app: The root application object
            config: The config for the specified tool
        """
        self._app = app
        self.config = config
        self._text_y = app.config["text_scroll_y"]
        self._description = None
        self._playbacks = []
        self._init_timer = None  # Timer used to apply a fade effect to the text
        self._replay_timer = time.time()

        self.name = self.config["name"]
        self.hold = config["hold"] if "hold" in config else False

        self.sounds = config["sounds"] if "sounds" in config else []
        self.sound_order = config["sound_order"] if "sound_order" in config else "random"
        self.sound_replay = config["sound_replay"] if "sound_replay" in config else 0
        self.sound_overlap = config["sound_overlap"] if "sound_overlap" in config else True

        self.descriptions = config["descriptions"] if "descriptions" in config else []
        self.background = config["background"] if "background" in config else app.config["default_background"]

        self.light_up = config["light"] if "light" in config else True
        self.motor_spin = config["motor"] if "motor" in config else True

        self.reset()
        self._loaded = False
    
    def reset(self):
        """ Resets all visual attributes of the tool """
        self._description_selector = 0
        if self.descriptions:
            self._update_description(self.descriptions[0])
        self._sound_selector = 0
        self._init_timer = time.time()
        self._stop_playbacks()
    
    def _stop_playbacks(self):
        """ Stops all current playbacks """
        for playback in self._playbacks:
            playback.stop()
        self._playbacks.clear()
    
    def is_loaded(self) -> bool:
        """ Returns True if the content has been loaded into the tool """
        return self._loaded

    def load_content(self):
        """ Loads all content for the given tool """
        assert not self._loaded, f"Content has already been loaded on tool {self.name}!"
        logging.debug(f"Loading all tool content for tool {self.name}")

        # Title text cache render
        text = self.name
        font_size = self._app.font.getsize(text)

        self._text_cache = Image.new("RGBA", (font_size[0]+5, font_size[1]+5), (0, 0, 0, 0))
        self._text_cache_yellow = Image.new("RGBA", (font_size[0]+5, font_size[1]+5), (0, 0, 0, 0))
        draw = ImageDraw.Draw(self._text_cache)
        draw_yellow = ImageDraw.Draw(self._text_cache_yellow)
        draw.text((4, 4), text, font=self._app.font, fill=(0, 0, 0))
        draw.text((0, 0), text, font=self._app.font, fill=(255, 255, 255))
        draw_yellow.text((4, 4), text, font=self._app.font, fill=(0, 0, 0))
        draw_yellow.text((0, 0), text, font=self._app.font, fill=(255, 205, 0))

        self._background = Image.open(content_relative(self.background))

        # Load all sounds used
        self._sounds = []
        for sound in self.sounds:
            if sound.endswith(".wav"):
                self._sounds.append(simpleaudio.WaveObject.from_wave_file(content_relative(sound)))
            else:
                raise Exception(f"Only wave files are supported ({sound})")

        self._loaded = True
        logging.debug(f"Loaded all tool content")
    
    def _play_sound(self):
        """ Plays the tools sound """
        sound = None
        if self.sound_order == "selective":
            self._sound_selector = (self._sound_selector+1)%len(self.sounds)
            sound = self._sounds[self._sound_selector]
        elif self.sound_order == "random":
            sound = random.choice(self._sounds)
        
        if sound:
            if not self.sound_overlap:
                self._stop_playbacks()
            self._playbacks.append(sound.play())
            self._replay_timer = time.time() + self.sound_replay
    
    def _update_description(self, text:str):
        """ Displays description on the toolgun
        Passing None will hide the text
        
        Args:
            text: The text to place on the toolgun
        """
        if text is None:
            self._description = None
        else:  # Render new description
            width = self._app.screen.width-20
            text_width = self._app.arial_font.getsize_multiline(text)[0]

            self._description = Image.new("RGB", (width, 30), (238, 240, 200))
            draw = ImageDraw.Draw(self._description)
            draw.line((0, 29, width, 29), fill=(0, 0, 0), width=4)
            draw.line((width-1, 0, width-1, 29), fill=(0, 0, 0), width=4)
            if "\n" in text:
                pos = 0
            else:
                pos = 7
            draw.text(((width//2) - (text_width//2), pos), text, (0, 0, 0), self._app.arial_font, align="center")

    
    def _manage_playbacks(self):
        """ Removes any finished playbacks """
        removes = []
        for playback in self._playbacks:
            if not playback.is_playing():
                removes.append(playback)
        for playback in removes:
            self._playbacks.remove(playback)

    def trigger(self):
        """ Called when the user fires the gun """
        # Tool description updates
        if self.descriptions:
            self._description_selector = (self._description_selector+1) % len(self.descriptions)
            self._update_description(self.descriptions[self._description_selector])
        
        # Play toolgun sounds
        if self.sounds:
            self._play_sound()
        
        # Clearup persistant playback objects
        self._manage_playbacks()

        if self.light_up:
            self._app.hardware.flash_led()

        if self.motor_spin:
            self._app.hardware.spin_motor()
    
    def loop(self):
        """ Called when the this tool has holding enabled """
        if self.sound_replay != 0 and time.time() > self._replay_timer and self.sounds:
            self._play_sound()
        
        if self.light_up:
            self._app.hardware.flash_led()
        
        if self.motor_spin:
            self._app.hardware.spin_motor()
        
        self._manage_playbacks()
    
    def render(self, screen:hardware.Screen):
        """ Renders the tool to the screen
        
        Args:
            screen: The screen to render to
        """
        assert self._loaded, "Tool content has not been loaded!!"

        screen.image.paste(self._background)

        # Draw moving text
        x_pos = screen.width - int((time.time()*160)%(self._text_cache.size[0]+(screen.width//2)))

        if self._init_timer is not None:
            render_text = Image.blend(self._text_cache_yellow, self._text_cache, min((time.time() - self._init_timer)/self.YELLOW_FADE_TIME, 1))
            if time.time() > self._init_timer + self.YELLOW_FADE_TIME:
                self._init_timer = None
        else:
            render_text = self._text_cache
        screen.image.paste(render_text, (x_pos, self._text_y), mask=self._text_cache)
        if x_pos-self._text_cache.size[0]-(screen.width//2)+self._text_cache.size[0] > 0:  # Render ghost
            screen.image.paste(render_text, (x_pos-self._text_cache.size[0]-(screen.width//2), self._text_y), mask=self._text_cache)

        if self._description is not None:
            screen.image.paste(self._description, (10, 73))

    def unload_content(self):
        """ Unloads all the content within this tool """
        self._text_cache = None
        self._sounds.clear()
        self._loaded = False


class App:
    """
      Toolgun application
      This app will drive the screen and display the various tools
       as well as play the sounds and events when the trigger is fired
    """
    MAX_TOOLS = 60  # Maximum tools that can be loaded into memory

    def __init__(self, config:dict, simulate:bool) -> None:
        """ Creates an instance of App
        
        Args:
            config: The application config
            simulate: Whether to tell all hardware interfaces to load simulators instead
        """
        self.config = config
        self._button_change = False
        self._current_tool = 0
        self._trigger_hold = None
        self._was_changing_tool = False  # Used to signify the tool was changed (plays sound)
        self._last_trigger = 0  # Used to time when the last trigger was (useful in switching from hold tools)
        self._sleep_mode = False
        self._sleep_timer = time.time() + config["sleep_timeout"]

        # Default content
        self.font = ImageFont.truetype(content_relative(config["font"]), config["font_size"])
        self.arial_font = ImageFont.truetype(content_relative("cour.ttf"), 12)
        self._next_item_sound = simpleaudio.WaveObject.from_wave_file(content_relative(config["sounds"]["next"]))
        self._equip_item_sound = simpleaudio.WaveObject.from_wave_file(content_relative(config["sounds"]["equip"]))
        self._startup_sound = simpleaudio.WaveObject.from_wave_file(content_relative(config["sounds"]["startup"]))
        
        # Hardware
        logging.debug("Init hardware")
        self.screen = hardware.Screen(config["hardware"], simulate)
        #if not simulate:
        #    self.screen.start_thread()
        self.hardware = hardware.GPHardware(config["hardware"], simulate)

        # Tools
        logging.debug("Init tools")
        self.tools = []
        for i, tool in enumerate(self.config["tools"]):
            self.tools.append(Tool(self, tool))
            if i < self.MAX_TOOLS:
                self.tools[-1].load_content()
    
    def play_startup(self):
        """ Plays the startup sound """
        self._startup_sound.play()
    
    def next_tool(self):
        """ Switches to the next tool and plays the switching audio """
        self.tools[self._current_tool].reset()
        self._current_tool = (self._current_tool+1) % len(self.tools)
        self.tools[self._current_tool].reset()

        self._was_changing_tool = True
        self._next_item_sound.play()
    
    def update(self):
        """ Update method for a single update tick """
        if not self._sleep_mode:
            self.tools[self._current_tool].render(self.screen)

        trigger_down = self.hardware.is_trigger_down()
        if trigger_down != self._button_change:
            self._button_change = trigger_down
            if self._button_change:
                self.tools[self._current_tool].trigger()
                self._trigger_hold = time.time()
            else:
                self._last_trigger, self._trigger_hold = self._trigger_hold, None
                if self._was_changing_tool:
                    self._was_changing_tool = False
                    self._equip_item_sound.play()
            
            self._sleep_timer = time.time() + self.config["sleep_timeout"]
            if self._sleep_mode:
                logging.info("Exiting sleep mode")
                self._sleep_mode = False
                if not self.screen._is_simulated:
                    self.screen.screen.bl_DutyCycle(100)
                self.screen.set_sleep(False)
            
        elif trigger_down and self.tools[self._current_tool].hold and not self._was_changing_tool:  # Holding tool
            self.tools[self._current_tool].loop()
            if time.time() - self._last_trigger < 0.5+self.config["tool_change_timeout"] and \
                time.time() > self._trigger_hold+self.config["tool_change_timeout"]:
                    self._trigger_hold = time.time()
                    self.next_tool()

        elif trigger_down and self._trigger_hold is not None and time.time() > self._trigger_hold+self.config["tool_change_timeout"]:  # Next tool
            self._trigger_hold = time.time()
            self.next_tool()
        
        if time.time() > self._sleep_timer and not self._sleep_mode:
            logging.info("No user input, entering sleep mode")
            self._sleep_mode = True
            if not self.screen._is_simulated:
                self.screen.screen.bl_DutyCycle(0)
            self.screen.set_sleep(True)

        self.hardware.update()
        self.screen.update()
    
    def teardown(self):
        """ Tears down the application """
        logging.critical("Tearing down application")
        self.screen.teardown()


def main():
    parser = argparse.ArgumentParser("Toolgun application")

    parser.add_argument("-config", default="config.json",
        help="The filepath to the json configuration")
    
    parser.add_argument("-simulate", action="store_true",
        help="Will load hardware hardware as simulated tkinter windows")
    
    parser.add_argument("-log_drop", action="store_true",
        help="Logs when the FPS of the application drops")

    args = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s [%(levelname)s]: %(message)s",
        level=logging.DEBUG
    )

    with open(args.config) as config_file:
        config = json.load(config_file)
    
    app = App(config, args.simulate)

    app.play_startup()

    next_frame = time.time()
    while True:
        try:
            app.update()
            
            if args.log_drop and next_frame - time.time() < 0:  # Log FPS drop
                logging.warn(f"FPS drop!! lost {abs(next_frame - time.time())} secs")

            time.sleep(max(next_frame - time.time(), 0))
            next_frame = time.time() + (1/config["refresh_rate"])
        except KeyboardInterrupt:
            logging.debug("Recieved keyboard interrupt")
            app.teardown()
            break


if __name__ == "__main__":
    main()
