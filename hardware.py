import logging
import time
import traceback
import threading
from PIL import Image as PImage
from PIL import ImageOps

tk_import = True
try:
    from tkinter import *
    from PIL import ImageTk as PImageTk
except:
    print("Failed to import tkinter, simulator disabled")
    traceback.print_exc()
    tk_import = False

hardware_import = True
try:
    import RPi.GPIO as GPIO
    from screen_lib import LCD_2inch4
except:
    print("Hardware import failed, hardware usage disabeld")
    traceback.print_exc()
    hardware_import = False


class Screen:
    """
      Interface for 2D screen, this can be either real or simulated
    """
    def __init__(self, config:dict, simulate=False) -> None:
        """ Creates an instance of Screen

        Args:
            config: The hardware config dictionary
            simulate: (OPTIONAL) Wheather this screen is siumulated (tk window)
        """
        self._config = config
        self._is_simulated = simulate
        self.__thread = None
        self.__thread_run = True
        self._sleep = False
        self.width = 240
        self.height = 320
        self.image = PImage.new("RGB", (240, 320), "black")
        self._image_buffer = PImage.new("RGB", (240, 320), "black")
        
        if simulate:
            assert tk_import, "Tkinter import has failed, cannot init"
            logging.debug("Initilizing screen simulator window")
            self.tk_root = Tk()
            self.tk_root.title("Virtual screen")

            self.tk_label = Label(self.tk_root)
            self.tk_label.pack(fill=BOTH)
        else:
            assert hardware_import, "Hardware import has failed, cannot init"

            self.screen = LCD_2inch4.LCD_2inch4()
            self.screen.Init()
            self.screen.clear()
    
    def set_sleep(self, is_sleep:bool):
        """ Turns the display off and stops rendering (sleep mode)
        
        Args:
            is_sleep: Whether to turn on/off sleep mode
        """
        self._sleep = is_sleep
        # TODO, backlight control
    
    def start_thread(self):
        """ Starts a thread that updates the screen """
        assert self.__thread is None, "A screen thread is still running!"

        self.__thread = threading.Thread(target=self.__thread_updator)
        self.__thread.start()
    
    def stop_thread(self):
        """ Signals the thread to stop """
        self.__thread_run = False
        logging.debug("Signalling thread close")
        self.__thread.join()
        logging.debug("Thread returned")

    def __thread_updator(self):
        """ Entry point for thread updator """
        next_frame = time.time()
        print("UPDATOR THREAD START")
        while self.__thread_run:
            self.update(True)
            time.sleep(max(next_frame - time.time(), 0))
            next_frame = time.time() + (1/self._config["screen_refresh"])
        print("UPDATOR THREAD END")
    
    def update(self, is_thread=False):
        """ Refreshed the display """
        if self.__thread and not is_thread:
            self._image_buffer.paste(self.image)
            return
        
        if self._is_simulated:
            self.tk_label.img = PImageTk.PhotoImage(self.image, master=self.tk_root)
            self.tk_label.config(image=self.tk_label.img)
            self.tk_label.update()
        elif not self._sleep:
            if is_thread:
                image = self._image_buffer
            else:
                image = self.image
            if self._config["screen_flip_horizontal"]:
                image = ImageOps.mirror(image)
            if self._config["screen_flip_vertical"]:
                image = ImageOps.flip(image)
            self.screen.ShowImage(image)
    
    def teardown(self):
        """ Tears down the screen interface """
        logging.debug("Tearing down screen interface")
        if self.__thread:
            self.stop_thread()
        if self._is_simulated:
            self.tk_root.destroy()
        else:
            self.screen.module_exit()

class GPHardware:
    """
      Simple hardware used accross the GPIO pins
    """

    def __init__(self, config, simulated=False) -> None:
        """ Creates an instance of GPHardware
        
        Args:
            config: The Hardware configuration
            simulated: (OPTIONAL) Whether to simulate all the hardware in a TK window
        """
        self.config = config
        self._motor_spin_end = None
        self._led_flash_end = None
        self._simulated = simulated
        
        if simulated:
            assert tk_import, "Tkinter import has failed, cannot init"
            logging.debug("Initilizing io simulator window")
            self.tk_root = Tk()
            self.tk_root.title("Hardware controls")

            self.led_state = Label(self.tk_root, text="LED: Off", fg="red")
            self.led_state.pack(side=TOP, anchor=W)
            self.motor_state = Label(self.tk_root, text="MOTOR: Off", fg="red")
            self.motor_state.pack(side=TOP, anchor=W)
            self.button_obj = Canvas(self.tk_root, width=30, height=30, bg="light gray")
            self.button_obj.bind("<Button-1>", self.__tk_but_on)
            self.button_obj.bind("<ButtonRelease-1>", self.__tk_but_off)
            self.button_obj.pack(side=TOP, anchor=W)
            self.button_state = False
        else:
            assert hardware_import, "Hardware import has failed, cannot init"
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.config["switch_pin"], GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(self.config["led_pin"], GPIO.OUT)
            GPIO.setup(self.config["motor_pin"], GPIO.OUT)
    
    def __tk_but_on(self, *ev):
        self.button_state = True
        self.button_obj.create_rectangle(0, 0, 50, 50, fill="red")

    def __tk_but_off(self, *ev):
        self.button_state = False
        self.button_obj.delete(ALL)
    
    def set_led(self, is_on:bool):
        """ Turns the LED on the end of the barrel on/off
        
        Args:
            is_on: Whether to turn the LED on/off
        """
        if self._simulated:
            self.led_state.config(text=f"LED: {'On' if is_on else 'Off'}", fg="green" if is_on else "red")
        else:
            GPIO.output(self.config["led_pin"], GPIO.HIGH if is_on else GPIO.LOW)
    
    def set_motor(self, is_on:bool):
        """ Turns the Motor on/off
        
        Args:
            is_on: Whether to turn the motor on/off
        """
        if self._simulated:
            self.motor_state.config(text=f"MOTOR: {'On' if is_on else 'Off'}", fg="green" if is_on else "red")
        else:
            GPIO.output(self.config["motor_pin"], GPIO.HIGH if is_on else GPIO.LOW)
    
    def spin_motor(self):
        """ Spins the motor for a brief period """
        self.set_motor(True)
        self._motor_spin_end = time.time() + self.config["spin_duration"]
    
    def flash_led(self):
        """ Flashed the led for a brief period """
        self.set_led(True)
        self._led_flash_end = time.time() + self.config["flash_duration"]
    
    def is_trigger_down(self) -> bool:
        """ Checks if the trigger is currently down
        
        Returns:
            bool: If the trigger is being fired
        """
        if self._simulated:
            return self.button_state
        else:
            if self.config["invert_button"]:
                return not GPIO.input(self.config["switch_pin"])
            return GPIO.input(self.config["switch_pin"])
    
    def update(self):
        """ Refreshed the display """
        if self._motor_spin_end is not None and time.time() > self._motor_spin_end:
            self._motor_spin_end = None
            self.set_motor(False)

        if self._led_flash_end is not None and time.time() > self._led_flash_end:
            self._led_flash_end = None
            self.set_led(False)
        
        if self._simulated:
            self.tk_root.update()
    
    def teardown(self):
        """ Tears down the screen interface """
        logging.debug("Tearing down screen interface")
        if self._simulated:
            self.tk_root.destroy()
        else:
            self.screen.module_exit()
            GPIO.cleanup()
