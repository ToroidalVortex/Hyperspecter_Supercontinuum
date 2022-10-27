''' Utility classes/functions
'''
import configparser
import os

import tifffile as tf
import numpy as np








########################
#    Math Utilities    #
########################

def gaussian(x,A=1,x0=0,sigma=1):
    y = A*np.exp(-((x-x0)**2)/(2*sigma**2))
    return y

def scale_min_max(array, minimum=None, maximum=None):
    ''' Scales data in array to range [0,1] where the minimum and maximum becomes 0 and 1, respectively. '''
    x = np.array(array, copy=True)
    mi = minimum if minimum else x.min()
    ma = maximum if maximum else x.max()
    return np.clip((x - mi)/(ma - mi), 0, 1)

def convert_to_16_bit(array, minimum=None, maximum=None):
    a = scale_min_max(array, minimum, maximum) * 2**16
    return a.astype(np.uint16)

def convert_to_8_bit(array, minimum=None, maximum=None):
    a = scale_min_max(array, minimum, maximum) * 2**8
    return a.astype(np.uint8)








##################################
#    Laser Scanning Utilities    #
##################################

def sawtooth(pixels: int, samples_per_pixel=1, number_of_lines=1):
    ''' Generates 'number_of_lines' linear ramps with 'pixels' values between -1 and 1. Each value is repeated 'samples_per_pixel' times. '''
    result = np.linspace(-1, 1, pixels)
    result = np.repeat(result, samples_per_pixel)
    result = np.tile(result, number_of_lines)
    return result

def triangle(pixels: int, samples_per_pixel=1, number_of_lines=1):
    ''' Takes the sawtooth wave and inverts every linear ramp. '''
    result = sawtooth(pixels, samples_per_pixel, number_of_lines)
    width = pixels * samples_per_pixel
    for i in range(1, number_of_lines, 2):
        start = i * width
        end = start + width
        # result[start:end] = [1-value for value in result[start:end]]
        result[start:end] = np.flip(result[start:end])
    return result

def generate_sawtooth_scan(resolution=(256,256), amplitude=10, offset=(0,0), fill_fraction=1.0, flyback=0, padding=(0,0)):
    ''' Generates the x- and y-axis control waveforms in the sawtooth pattern.
    
    Inputs:
        resolution (int: x_pixels, int: y_pixels): number of pixels in each dimension of the image.
        amplitude: voltage amplitude of the 'acquired' segment of the scan. The actual waveform will extend beyond this according to fill_fraction. 
            Since fill_fraction would cause horizontal zooming if we simply kept the same overall amplitude, I scale the actual amplitude up so that
            the portion of the scan that is kept stays within the same voltage window. 
        offset: the voltage offset (x_offset, y_offset)
        fill_fraction (float): (0,1] ratio between the acquired samples and total samples in the laser scan path.
            Although shutters can be used to block the beam and acquisition can be toggled, it is practical
            to record all samples and simply remove the extra samples in post-processing. 

            fill_fraction = resolution / total_samples
        
        flyback (int): number of flyback samples.
        padding (int: start, int: end): tuple containing the number of samples to add to the start and end of the waveforms.
    
    Returns:
        x_data: x-axis scan data in the form [x1, x2, x3, ..., xN]
        y_data: y-axis scan data in the form [y1, y2, y3, ..., yN]
        samples_per_line: the number of pixels in each line, to be used to calculate clock rate for line period
        throwaway: the number of samples at the beginning of each line to ignore
        flyback: the number of samples at the end of each line to ignore

    '''
    # Get sizes of x-axis line scan segments
    total_scan = int(resolution[0] / fill_fraction)
    throwaway = total_scan - resolution[0]
    samples_per_line = total_scan + flyback
    
    # Create x-axis waveform
    total_amplitude = amplitude / fill_fraction
    ff_offset = (1-fill_fraction) * total_amplitude
    total_offset = ff_offset + offset[0]
    x_scan = total_amplitude * sawtooth(total_scan) - total_offset
    x_flyback = generate_flyback(total_amplitude, total_offset, flyback)
    x_data = np.tile(np.concatenate([x_scan, x_flyback]), resolution[1])
    
    # Create y-axis waveform
    y_data = amplitude * sawtooth(resolution[1], samples_per_line) - offset[1]

    assert x_data.size == y_data.size, 'X and Y should have the same size.'
    
    # Clip data outside of the -10V to +10V range allowed by the galvos
    x_data = np.clip(x_data, -10, 10)
    y_data = np.clip(y_data, -10, 10)

    # Add padding at start and end of waveforms
    x_data = np.concatenate((np.full(padding[0],x_data[0]), x_data, np.full(padding[1],x_data[-1])))
    y_data = np.concatenate((np.full(padding[0],y_data[0]), y_data, np.full(padding[1],y_data[-1])))
    
    return x_data, y_data, samples_per_line, throwaway, flyback, padding


def generate_bidirectional_scan(resolution=(256,256), amplitude=10, offset=(0,0), fill_fraction=1.0, padding=(0,0)):
    ''' Generates the x- and y-axis control waveforms in the bidirectional pattern.
    
    Inputs:
        resolution (int: x_pixels, int: y_pixels): number of pixels in each dimension of the image.
        amplitude: voltage amplitude of the 'acquired' segment of the scan. The actual waveform will extend beyond this according to fill_fraction. 
            Since fill_fraction would cause horizontal zooming if we simply kept the same overall amplitude, I scale the actual amplitude up so that
            the portion of the scan that is kept stays within the same voltage window. 
        offset: the voltage offset (x_offset, y_offset)
        fill_fraction (float): (0,1] ratio between the acquired samples and total samples in the laser scan path.
            Although shutters can be used to block the beam and acquisition can be toggled, it is practical
            to record all samples and simply remove the extra samples in post-processing. 

            fill_fraction = resolution / total_samples

        padding (int: start, int: end): tuple containing the number of samples to add to the start and end of the waveforms.
    
    Returns:
        x_data: x-axis scan data in the form [x1, x2, x3, ..., xN]
        y_data: y-axis scan data in the form [y1, y2, y3, ..., yN]
        samples_per_line: the number of pixels in each line, to be used to calculate clock rate for line period
        throwaway: the number of samples at the beginning and end of each line to ignore

    '''
    # Get sizes of x-axis line scan segments
    total_scan = int(resolution[0] / fill_fraction)
    throwaway = int(0.5*(total_scan - resolution[0]))
    samples_per_line = total_scan
    
    # Create x-axis waveform
    total_amplitude = amplitude / fill_fraction
    x_data = total_amplitude * triangle(total_scan, 1, resolution[1]) - offset[0]
    
    # Create y-axis waveform
    y_data = amplitude * sawtooth(resolution[1], samples_per_line) - offset[1]

    assert x_data.size == y_data.size, 'X and Y should have the same size.'
    
    # Clip data outside of the -10V to +10V range allowed by the galvos
    x_data = np.clip(x_data, -10, 10)
    y_data = np.clip(y_data, -10, 10)

    # Add padding at start and end of waveforms
    x_data = np.concatenate((np.full(padding[0],x_data[0]), x_data, np.full(padding[1],x_data[-1])))
    y_data = np.concatenate((np.full(padding[0],y_data[0]), y_data, np.full(padding[1],y_data[-1])))
    
    return x_data, y_data, samples_per_line, throwaway, padding



def generate_flyback(amplitude=10, offset=0, pixels=256):
    x = np.linspace(0, np.pi, pixels)
    flyback = amplitude * np.cos(x) - offset
    return flyback


def estimate_imaging_time(start, stop, step_size, frame_time=1.28):
    ''' Estimates scan time. '''
    diff = np.abs(stop - start) + 1
    number_of_frames = np.ceil(diff / step_size)
    time = number_of_frames * frame_time
    return time









#############################
#    Saving/Loading Data    #
#############################

def save_settings(fname, settings):
    with open(fname, 'w') as file:
        for k, v in settings.items():
            file.write(f'{k} = {v}\n')

def save_config(fname, config):
    ''' Save a dictionary as a config file. '''
    parser = configparser.ConfigParser()
    
    for section in config.keys():
        parser.add_section(section)
        for key, val in config[section].items():
            parser.set(str(section), str(key), str(val))
    
    with open(fname, 'w') as config_file:
        parser.write(config_file)

def load_config(fname):
    parser = configparser.ConfigParser()
    parser.read(fname)
    
    config = {}
    for section in parser.sections():
        config[section] = {}
        for key, val in parser[section].items():
            config[section][key] = val

    return config









if __name__ == '__main__':
    import matplotlib.pyplot as plt

    #### Test sawtooth ####
    
    # x_pixels = 5
    # y_pixels = 5
    # samples_per_pixel = 5
    
    # saw = sawtooth(x_pixels, samples_per_pixel, y_pixels)
    # tri = triangle(x_pixels, samples_per_pixel, y_pixels)

    # plt.figure()
    # plt.plot(saw)
    # plt.plot(tri)
    # plt.show()


    # x_data, y_data, _, _, _, _ = generate_sawtooth_scan(resolution=(30,5), amplitude=2, offset=(-5,0), fill_fraction=0.5, flyback=0, delay=(100,100))
    # x_data, y_data, _, _, _ = generate_bidirectional_scan(resolution=(30,5), amplitude=2, offset=(0,0), fill_fraction=0.5, delay=(100,100))

    # plt.figure()
    # plt.plot(x_data)
    # plt.plot(y_data)
    # plt.show()

    # arr = np.arange(10)
    # arr = scale_min_max(arr, 2, 8)
    # print(arr)

    start = 750
    stop = 980
    step = 1
    time = estimate_imaging_time(start, stop, step)
    print(time)

    ########################

