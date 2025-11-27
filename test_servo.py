import time 
from adafruit_servokit import ServoKit

# Set channels to the number of servo channels on your kit.
# 8 for FeatherWing, 16 for Shield/HAT/Bonnet.
kit = ServoKit(channels=16)
servo = 0
while True:
    a=input("Enter angle (0-180): ")
    kit.servo[0].angle = int(a)