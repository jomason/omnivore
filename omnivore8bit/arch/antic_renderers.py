import numpy as np

import wx

from atrcopy import match_bit_mask, comment_bit_mask, selected_bit_mask, diff_bit_mask, user_bit_mask, not_user_bit_mask

from omnivore.utils.permute import bit_reverse_table
from omnivore.utils.nputil import intscale, intwscale, intwscale_font

import colors
from atascii import internal_to_atascii, atascii_to_internal
try:
    import antic_speedups as speedups
except ImportError:
    speedups = None

import logging
log = logging.getLogger(__name__)


class BaseRenderer(object):
    name = "base"
    scale_width = 1
    scale_height = 1
    pixels_per_byte = 8
    bitplanes = 1
    ignore_mask = not_user_bit_mask & (0xff ^ diff_bit_mask)

    def __eq__(self, other):
        try:
            return other is not None and self.name == other.name and self.pixels_per_byte == other.pixels_per_byte and self.bitplanes == other.bitplanes
        except AttributeError:
            pass
        return False

    def validate_bytes_per_row(self, bytes_per_row):
        return bytes_per_row

    def get_colors(self, segment_viewer, registers):
        color_registers = [segment_viewer.machine.color_registers[r] for r in registers]
        h_colors = colors.get_blended_color_registers(color_registers, segment_viewer.preferences.highlight_background_color)
        m_colors = colors.get_blended_color_registers(color_registers, segment_viewer.preferences.match_background_color)
        c_colors = colors.get_blended_color_registers(color_registers, segment_viewer.preferences.comment_background_color)
        d_colors = colors.get_dimmed_color_registers(color_registers, segment_viewer.preferences.background_color, segment_viewer.preferences.data_background_color)
        return color_registers, h_colors, m_colors, c_colors, d_colors

    def reshape(self, bitimage, bytes_per_row, nr):
        # source array 'bitimage' in the shape of (size, w, 3)
        h, w, colors = bitimage.shape
        # create a new image with pixels in the correct aspect ratio
        output = bitimage.reshape((nr, self.pixels_per_byte * bytes_per_row, 3))
        output = intscale(output, self.scale_height, self.scale_width)
        log.debug("bitimage: %d,%d,%d; ppb=%d bpr=%d, output=%s" % (h, w, colors, self.pixels_per_byte * self.scale_width, bytes_per_row, str(output.shape)))
        return output

    def get_2bpp(self, segment_viewer, bytes_per_row, nr, count, bytes, style, colors):
        bits = np.unpackbits(bytes)
        bits = bits.reshape((-1, 8))
        pixels = np.empty((nr * bytes_per_row, 4), dtype=np.uint8)
        pixels[:,0] = bits[:,0] * 2 + bits[:,1]
        pixels[:,1] = bits[:,2] * 2 + bits[:,3]
        pixels[:,2] = bits[:,4] * 2 + bits[:,5]
        pixels[:,3] = bits[:,6] * 2 + bits[:,7]

        style_per_pixel = np.vstack((style, style, style, style)).T
        normal = (style_per_pixel & self.ignore_mask) == 0
        highlight = (style_per_pixel & selected_bit_mask) == selected_bit_mask
        data = (style_per_pixel & user_bit_mask) > 0
        comment = (style_per_pixel & comment_bit_mask) == comment_bit_mask
        match = (style_per_pixel & match_bit_mask) == match_bit_mask

        color_registers, h_colors, m_colors, c_colors, d_colors = colors
        bitimage = np.empty((nr * bytes_per_row, 4, 3), dtype=np.uint8)
        for i in range(4):
            color_is_set = (pixels == i)
            bitimage[color_is_set & normal] = color_registers[i]
            bitimage[color_is_set & data] = d_colors[i]
            bitimage[color_is_set & comment] = c_colors[i]
            bitimage[color_is_set & match] = m_colors[i]
            bitimage[color_is_set & highlight] = h_colors[i]
        bitimage[count:,:,:] = segment_viewer.preferences.empty_background_color.Get(False)
        return bitimage

    def get_4bpp(self, segment_viewer, bytes_per_row, nr, count, bytes, style, colors):
        bits = np.unpackbits(bytes)
        bits = bits.reshape((-1, 8))
        pixels = np.empty((nr * bytes_per_row, 2), dtype=np.uint8)
        pixels[:,0] = bits[:,0] * 8 + bits[:,1] * 4 + bits[:,2] * 2 + bits[:,3]
        pixels[:,1] = bits[:,4] * 8 + bits[:,5] * 4 + bits[:,6] * 2 + bits[:,7]

        style_per_pixel = np.vstack((style, style)).T
        normal = (style_per_pixel & self.ignore_mask) == 0
        highlight = (style_per_pixel & selected_bit_mask) == selected_bit_mask
        data = (style_per_pixel & user_bit_mask) > 0
        comment = (style_per_pixel & comment_bit_mask) == comment_bit_mask
        match = (style_per_pixel & match_bit_mask) == match_bit_mask

        color_registers, h_colors, m_colors, c_colors, d_colors = colors
        bitimage = np.empty((nr * bytes_per_row, 2, 3), dtype=np.uint8)
        for i in range(16):
            color_is_set = (pixels == i)
            bitimage[color_is_set & normal] = color_registers[i]
            bitimage[color_is_set & data] = d_colors[i]
            bitimage[color_is_set & comment] = c_colors[i]
            bitimage[color_is_set & match] = m_colors[i]
            bitimage[color_is_set & highlight] = h_colors[i]
        bitimage[count:,:,:] = segment_viewer.preferences.empty_background_color.Get(False)
        return bitimage

    def get_bitplane_pixels(self, bits, pixels, bytes_per_row, pixels_per_row):
        """Fill the pixels array with color register data
        
        pixels is passed in as an 8 pixel wide array regardless of the actual
        pixels per row. It will be resized correctly by the calling method.
        """
        raise NotImplemented

    def get_bitplane_style(self, style):
        raise NotImplemented

    def get_bitplanes(self, segment_viewer, bytes_per_row, nr, count, bytes, style, colors):
        bitplanes = self.bitplanes
        _, rem = divmod(np.alen(bytes), bitplanes)
        if rem > 0:
            bytes = np.append(bytes, np.zeros(rem, dtype=np.uint8))
            style = np.append(style, np.zeros(rem, dtype=np.uint8))
        pixels_per_row = 8 * bytes_per_row / bitplanes
        bits = np.unpackbits(bytes).reshape((-1, 8))
        pixels = np.empty((nr * bytes_per_row / bitplanes, pixels_per_row), dtype=np.uint8)
        self.get_bitplane_pixels(bits, pixels, bytes_per_row, pixels_per_row)
        pixels = pixels.reshape((nr, pixels_per_row))
        s = self.get_bitplane_style(style)
        style_per_pixel = s.repeat(8).reshape((-1, pixels_per_row))
        normal = (style_per_pixel & self.ignore_mask) == 0
        highlight = (style_per_pixel & selected_bit_mask) == selected_bit_mask
        data = (style_per_pixel & user_bit_mask) > 0
        comment = (style_per_pixel & comment_bit_mask) == comment_bit_mask
        match = (style_per_pixel & match_bit_mask) == match_bit_mask

        color_registers, h_colors, m_colors, c_colors, d_colors = colors
        bitimage = np.empty((nr, pixels_per_row, 3), dtype=np.uint8)
        for i in range(2**bitplanes):
            color_is_set = (pixels == i)
            bitimage[color_is_set & normal] = color_registers[i]
            bitimage[color_is_set & data] = d_colors[i]
            bitimage[color_is_set & comment] = c_colors[i]
            bitimage[color_is_set & match] = m_colors[i]
            bitimage[color_is_set & highlight] = h_colors[i]
        bitimage[count:,:,:] = segment_viewer.preferences.empty_background_color.Get(False)
        return bitimage


class OneBitPerPixelB(BaseRenderer):
    name = "B/W, 1bpp, on=black"

    def get_bw_colors(self, segment_viewer):
        return ((255, 255, 255), (0, 0, 0))

    def get_image(self, segment_viewer, bytes_per_row, nr, count, bytes, style):
        bits = np.unpackbits(bytes)
        pixels = bits.reshape((-1, 8))

        background = (pixels == 0)
        color1 = (pixels == 1)

        bw_colors = self.get_bw_colors(segment_viewer)
        h_colors = colors.get_blended_color_registers(bw_colors, segment_viewer.preferences.highlight_background_color)
        m_colors = colors.get_blended_color_registers(bw_colors, segment_viewer.preferences.match_background_color)
        c_colors = colors.get_blended_color_registers(bw_colors, segment_viewer.preferences.comment_background_color)
        d_colors = colors.get_dimmed_color_registers(bw_colors, segment_viewer.preferences.background_color, segment_viewer.preferences.data_background_color)

        style_per_pixel = np.vstack((style, style, style, style, style, style, style, style)).T
        normal = (style_per_pixel & self.ignore_mask) == 0
        highlight = (style_per_pixel & selected_bit_mask) == selected_bit_mask
        data = (style_per_pixel & user_bit_mask) > 0
        comment = (style_per_pixel & comment_bit_mask) == comment_bit_mask
        match = (style_per_pixel & match_bit_mask) == match_bit_mask

        bitimage = np.empty((nr * bytes_per_row, 8, 3), dtype=np.uint8)
        bitimage[background & normal] = bw_colors[0]
        bitimage[background & data] = d_colors[0]
        bitimage[background & comment] = c_colors[0]
        bitimage[background & match] = m_colors[0]
        bitimage[background & highlight] = h_colors[0]
        bitimage[color1 & normal] = bw_colors[1]
        bitimage[color1 & data] = d_colors[1]
        bitimage[color1 & comment] = c_colors[1]
        bitimage[color1 & match] = m_colors[1]
        bitimage[color1 & highlight] = h_colors[1]
        bitimage[count:,:,:] = segment_viewer.preferences.empty_background_color.Get(False)

        return self.reshape(bitimage, bytes_per_row, nr)


class OneBitPerPixelW(OneBitPerPixelB):
    name = "B/W, 1bpp, on=white"

    def get_bw_colors(self, segment_viewer):
        return ((0, 0, 0), (255, 255, 255))


class OneBitPerPixelPM1(OneBitPerPixelB):
    name = "Player/Missile, normal width"
    scale_width = 2


class OneBitPerPixelPM2(OneBitPerPixelB):
    name = "Player/Missile, double width"
    scale_width = 4


class OneBitPerPixelPM4(OneBitPerPixelB):
    name = "Player/Missile, quad width"
    scale_width = 8


class ModeB(OneBitPerPixelB):
    name = "Antic B (Gr 6, 1bpp)"
    scale_width = 2
    scale_height = 2

    def get_bw_colors(self, segment_viewer):
        color_registers = [segment_viewer.machine.color_registers[r] for r in [8, 4]]
        return color_registers


class ModeC(ModeB):
    name = "Antic C (Gr 6+, 1bpp)"
    scale_width = 2
    scale_height = 2


class OneBitPerPixelApple2Linear(BaseRenderer):
    name = "B/W, Apple 2, Linear"

    def get_bw_colors(self, segment_viewer):
        return ((0, 0, 0), (255, 255, 255))

    def get_image(self, segment_viewer, bytes_per_row, nr, count, bytes, style):
        bits = np.unpackbits(bit_reverse_table[bytes])
        pixels = bits.reshape((-1, 8))

        background = (pixels[:,0:7] == 0)
        color1 = (pixels[:,0:7] == 1)

        bw_colors = self.get_bw_colors(segment_viewer)
        h_colors = colors.get_blended_color_registers(bw_colors, segment_viewer.preferences.highlight_background_color)
        m_colors = colors.get_blended_color_registers(bw_colors, segment_viewer.preferences.match_background_color)
        c_colors = colors.get_blended_color_registers(bw_colors, segment_viewer.preferences.comment_background_color)
        d_colors = colors.get_dimmed_color_registers(bw_colors, segment_viewer.preferences.background_color, segment_viewer.preferences.data_background_color)

        style_per_pixel = np.vstack((style, style, style, style, style, style, style)).T
        normal = (style_per_pixel & self.ignore_mask) == 0
        highlight = (style_per_pixel & selected_bit_mask) == selected_bit_mask
        data = (style_per_pixel & user_bit_mask) > 0
        comment = (style_per_pixel & comment_bit_mask) == comment_bit_mask
        match = (style_per_pixel & match_bit_mask) == match_bit_mask

        bitimage = np.empty((nr * bytes_per_row, 7, 3), dtype=np.uint8)
        bitimage[background & normal] = bw_colors[0]
        bitimage[background & data] = d_colors[0]
        bitimage[background & comment] = c_colors[0]
        bitimage[background & match] = m_colors[0]
        bitimage[background & highlight] = h_colors[0]
        bitimage[color1 & normal] = bw_colors[1]
        bitimage[color1 & data] = d_colors[1]
        bitimage[color1 & comment] = c_colors[1]
        bitimage[color1 & match] = m_colors[1]
        bitimage[color1 & highlight] = h_colors[1]
        bitimage[count:,:,:] = segment_viewer.preferences.empty_background_color.Get(False)

        return bitimage.reshape((nr, bytes_per_row * 7, 3))


def generate_apple2_row_offsets():
    offsets = np.zeros(192, dtype=np.int32)
    for y in range(192):
        # From Apple Graphics and Arcade Game Design
        a = y // 64
        d = y - (64 * a)
        b = d // 8
        c = d - 8 * b
        offsets[i] = (1024 * c) + (128 * b) + (40 * a)
    return offsets

def generate_apple2_index():
    offsets = generate_apple2_row_offsets()
    bytepos = np.empty((192, 280), dtype=np.int32)
    bytepos[:,0] = offsets * 7

class OneBitPerPixelApple2FullScreen(BaseRenderer):
    name = "B/W, Apple 2, Screen Order"

    def get_bw_colors(self, segment_viewer):
        return ((0, 0, 0), (255, 255, 255))

    def get_image(self, segment_viewer, bytes_per_row, nr, count, bytes, style):
        screen = np.zeros((8192,), dtype=np.uint8)
        bytes = bytes[0:8192]
        num_valid = len(bytes)  # might be smaller than 8192
        screen[:num_valid] = bytes
        bits = np.unpackbits(bit_reverse_table[screen])
        pixels = bits.reshape((-1, 8))

        background = (pixels[:,0:7] == 0)
        color1 = (pixels[:,0:7] == 1)

        bw_colors = self.get_bw_colors(segment_viewer)
        h_colors = colors.get_blended_color_registers(bw_colors, segment_viewer.preferences.highlight_background_color)
        m_colors = colors.get_blended_color_registers(bw_colors, segment_viewer.preferences.match_background_color)
        c_colors = colors.get_blended_color_registers(bw_colors, segment_viewer.preferences.comment_background_color)
        d_colors = colors.get_dimmed_color_registers(bw_colors, segment_viewer.preferences.background_color, segment_viewer.preferences.data_background_color)

        style_per_pixel = np.vstack((style, style, style, style, style, style, style)).T
        normal = (style_per_pixel & self.ignore_mask) == 0
        highlight = (style_per_pixel & selected_bit_mask) == selected_bit_mask
        data = (style_per_pixel & user_bit_mask) > 0
        comment = (style_per_pixel & comment_bit_mask) == comment_bit_mask
        match = (style_per_pixel & match_bit_mask) == match_bit_mask

        bitimage = np.empty((192 * 40, 7, 3), dtype=np.uint8)
        bitimage[background & normal] = bw_colors[0]
        bitimage[background & data] = d_colors[0]
        bitimage[background & comment] = c_colors[0]
        bitimage[background & match] = m_colors[0]
        bitimage[background & highlight] = h_colors[0]
        bitimage[color1 & normal] = bw_colors[1]
        bitimage[color1 & data] = d_colors[1]
        bitimage[color1 & comment] = c_colors[1]
        bitimage[color1 & match] = m_colors[1]
        bitimage[color1 & highlight] = h_colors[1]
        bitimage[count:,:,:] = segment_viewer.preferences.empty_background_color.Get(False)

        return bitimage.reshape((nr, bytes_per_row * 7, 3))


class OneBitPerPixelApple2Artifacting(BaseRenderer):
    name = "Apple 2 (artifacting colors)"

    def get_bw_colors(self, segment_viewer):
        return ((255, 255, 255), (0, 0, 0))

    # 0 0000000 0 0000000  # black 0, 0, 0
    # 0 0101010 0 1010101  # green 32, 192, 0
    # 0 1010101 0 0101010  # purple 159, 0, 253
    # 0 1111111 0 1111111  # white 255, 255, 255
    # 1 0000000 1 0000000  # black 0, 0, 0
    # 1 0101010 1 1010101  # orange 240, 80, 0
    # 1 1010101 1 0101010  # blue 0, 128, 255
    # 1 1111111 1 1111111  # white 255, 255, 255
    #
    # From https://groups.google.com/forum/#!msg/comp.sys.apple2.programmer/vxtFo6QEYGg/9kh1RfovGQAJ
    # bit #
    # 0 1 2 3 4 5 6 7   0 1 2 3 4 5 6 7

    #          color bit          color bit
    #               |                 |
    # 0 0 0 0 0 0 0 0   0 0 0 0 0 0 0 0
    # |_| |_| |_| |_____| |_| |_| |_|

    #  0   1   2     3     4   5   6

    # every 2 bytes starting on an even number ($2000.2001) gives seven pixels.
    # As you can see, pixel #3 uses a bit from byte $2000 and byte 2001 to form
    # a pixel. if any two bits are consecutive (except the color bit) you get
    # two white pixels. with color bit clear, each group of bits will show
    # violet or green. with color bit set, each group of bits will show blue or
    # orange.

    # color bit clear
    # bits-color
    # 00 - black
    # 10 - violet
    # 01 - green
    # 11 - white

    # color bit set
    # 00 - black
    # 10 - blue
    # 01 - orange
    # 11 - white

    def get_image(self, segment_viewer, bytes_per_row, nr, count, bytes, style):
        bits = np.unpackbits(bit_reverse_table[bytes])
        pixels = bits.reshape((-1, 8))

        background = (pixels[:,0:7] == 0)
        color1 = (pixels[:,0:7] == 1)

        bw_colors = self.get_bw_colors(segment_viewer)
        h_colors = colors.get_blended_color_registers(bw_colors, segment_viewer.preferences.highlight_background_color)
        m_colors = colors.get_blended_color_registers(bw_colors, segment_viewer.preferences.match_background_color)
        c_colors = colors.get_blended_color_registers(bw_colors, segment_viewer.preferences.comment_background_color)
        d_colors = colors.get_dimmed_color_registers(bw_colors, segment_viewer.preferences.background_color, segment_viewer.preferences.data_background_color)

        style_per_pixel = np.vstack((style, style, style, style, style, style, style)).T
        normal = (style_per_pixel & self.ignore_mask) == 0
        highlight = (style_per_pixel & selected_bit_mask) == selected_bit_mask
        data = (style_per_pixel & user_bit_mask) > 0
        comment = (style_per_pixel & comment_bit_mask) == comment_bit_mask
        match = (style_per_pixel & match_bit_mask) == match_bit_mask

        bitimage = np.empty((nr * bytes_per_row, 7, 3), dtype=np.uint8)
        bitimage[background & normal] = bw_colors[0]
        bitimage[background & data] = d_colors[0]
        bitimage[background & comment] = c_colors[0]
        bitimage[background & match] = m_colors[0]
        bitimage[background & highlight] = h_colors[0]
        bitimage[color1 & normal] = bw_colors[1]
        bitimage[color1 & data] = d_colors[1]
        bitimage[color1 & comment] = c_colors[1]
        bitimage[color1 & match] = m_colors[1]
        bitimage[color1 & highlight] = h_colors[1]
        bitimage[count:,:,:] = segment_viewer.preferences.empty_background_color.Get(False)

        return bitimage.reshape((nr, bytes_per_row * 7, 3))


class TwoBitsPerPixel(BaseRenderer):
    name = "2bpp"
    pixels_per_byte = 4

    def get_image(self, segment_viewer, bytes_per_row, nr, count, bytes, style):
        colors = self.get_colors(segment_viewer, [0, 1, 2, 3])
        bitimage = self.get_2bpp(segment_viewer, bytes_per_row, nr, count, bytes, style, colors)
        return self.reshape(bitimage, bytes_per_row, nr)


class ModeD(TwoBitsPerPixel):
    name = "Antic D (Gr 7, 2bpp)"
    scale_width = 2
    scale_height = 2
    pixels_per_byte = 4

    def get_image(self, segment_viewer, bytes_per_row, nr, count, bytes, style):
        colors = self.get_colors(segment_viewer, [8, 4, 5, 6])
        bitimage = self.get_2bpp(segment_viewer, bytes_per_row, nr, count, bytes, style, colors)
        return self.reshape(bitimage, bytes_per_row, nr)


class ModeE(ModeD):
    name = "Antic E (Gr 7+, 2bpp)"
    scale_width = 2
    scale_height = 1
    pixels_per_byte = 4


class FourBitsPerPixel(BaseRenderer):
    name = "4bpp"
    pixels_per_byte = 2

    def get_image(self, segment_viewer, bytes_per_row, nr, count, bytes, style):
        colors = self.get_colors(segment_viewer, range(16))
        bitimage = self.get_4bpp(segment_viewer, bytes_per_row, nr, count, bytes, style, colors)
        return self.reshape(bitimage, bytes_per_row, nr)


class TwoBitPlanesLE(BaseRenderer):
    name = "2 Bit Planes (little endian)"
    pixels_per_byte = 8
    bitplanes = 2

    def get_bitplane_pixels(self, bits, pixels, bytes_per_row, pixels_per_row):
        for i in range(pixels_per_row):
            pixels[:,i] = bits[0::2,i] + bits[1::2,i] * 2

    def get_bitplane_style(self, style):
        return style[0::2] | style[1::2]

    def validate_bytes_per_row(self, bytes_per_row):
        scale, rem = divmod(bytes_per_row, self.bitplanes)
        if rem > 0:
            bytes_per_row = (scale + 1) * self.bitplanes
        return bytes_per_row

    def get_image(self, segment_viewer, bytes_per_row, nr, count, bytes, style):
        colors = self.get_colors(segment_viewer, range(2**self.bitplanes))
        bitimage = self.get_bitplanes(segment_viewer, bytes_per_row, nr, count, bytes, style, colors)
        return bitimage


class TwoBitPlanesBE(TwoBitPlanesLE):
    name = "2 Bit Planes (big endian)"

    def get_bitplane_pixels(self, bits, pixels, bytes_per_row, pixels_per_row):
        for i in range(pixels_per_row):
            pixels[:,i] = bits[0::2,i] * 2 + bits[1::2,i]


class TwoBitPlanesLineLE(TwoBitPlanesLE):
    name = "2 Bit Planes (little endian, interleave by line)"

    def get_bitplane_pixels(self, bits, pixels, bytes_per_row, pixels_per_row):
        pixel_rows = bytes_per_row / 2
        for i in range(pixels_per_row):
            for j in range(pixel_rows):
                little = j
                big = j + pixel_rows
                pixels[j::pixel_rows,i] = bits[big::bytes_per_row,i] * 2 + bits[little::bytes_per_row,i]


class TwoBitPlanesLineBE(TwoBitPlanesLE):
    name = "2 Bit Planes (big endian, interleave by line)"

    def get_bitplane_pixels(self, bits, pixels, bytes_per_row, pixels_per_row):
        pixel_rows = bytes_per_row / 2
        for i in range(pixels_per_row):
            for j in range(pixel_rows):
                little = j + pixel_rows
                big = j
                pixels[j::pixel_rows,i] = bits[big::bytes_per_row,i] * 2 + bits[little::bytes_per_row,i]


class ThreeBitPlanesLE(TwoBitPlanesLE):
    name = "3 Bit Planes (little endian)"
    bitplanes = 3

    def get_bitplane_pixels(self, bits, pixels, bytes_per_row, pixels_per_row):
        for i in range(pixels_per_row):
            pixels[:,i] = bits[0::3,i] * 4 + bits[1::3,i] * 2 + bits[2::3,i]

    def get_bitplane_style(self, style):
        return style[0::3] | style[1::3] | style[2::3]


class ThreeBitPlanesBE(ThreeBitPlanesLE):
    name = "3 Bit Planes (big endian)"
    bitplanes = 3

    def get_bitplane_pixels(self, bits, pixels, bytes_per_row, pixels_per_row):
        for i in range(pixels_per_row):
            pixels[:,i] = bits[0::3,i] + bits[1::3,i] * 2 + bits[2::3,i] * 4


class ThreeBitPlanesLineLE(ThreeBitPlanesLE):
    name = "3 Bit Planes (little endian, interleave by line)"

    def get_bitplane_pixels(self, bits, pixels, bytes_per_row, pixels_per_row):
        pixel_rows = bytes_per_row / 3
        for i in range(pixels_per_row):
            for j in range(pixel_rows):
                little = j
                mid = j + pixel_rows
                big = j + (2 * pixel_rows)
                pixels[j::pixel_rows,i] = bits[big::bytes_per_row,i] * 4 + bits[mid::bytes_per_row,i] * 2 + bits[little::bytes_per_row,i]


class ThreeBitPlanesLineBE(ThreeBitPlanesBE):
    name = "3 Bit Planes (big endian, interleave by line)"

    def get_bitplane_pixels(self, bits, pixels, bytes_per_row, pixels_per_row):
        pixel_rows = bytes_per_row / 3
        for i in range(pixels_per_row):
            for j in range(pixel_rows):
                little = j + (2 * pixel_rows)
                mid = j + pixel_rows
                big = j
                pixels[j::pixel_rows,i] = bits[big::bytes_per_row,i] * 4 + bits[mid::bytes_per_row,i] * 2 + bits[little::bytes_per_row,i]


class FourBitPlanesLE(TwoBitPlanesLE):
    name = "4 Bit Planes (little endian)"
    bitplanes = 4

    def get_bitplane_pixels(self, bits, pixels, bytes_per_row, pixels_per_row):
        for i in range(pixels_per_row):
            pixels[:,i] = bits[0::4,i] * 8 + bits[1::4,i] * 4 + bits[2::4,i] * 2 + bits[3::4,i]

    def get_bitplane_style(self, style):
        return style[0::4] | style[1::4] | style[2::4] | style[3::4]


class FourBitPlanesBE(FourBitPlanesLE):
    name = "4 Bit Planes (big endian)"

    def get_bitplane_pixels(self, bits, pixels, bytes_per_row, pixels_per_row):
        for i in range(pixels_per_row):
            pixels[:,i] = bits[0::4,i] + bits[1::4,i] * 2 + bits[2::4,i] * 4 + bits[3::4,i] * 8


class FourBitPlanesLineLE(FourBitPlanesLE):
    name = "4 Bit Planes (little endian, interleave by line)"

    def get_bitplane_pixels(self, bits, pixels, bytes_per_row, pixels_per_row):
        pixel_rows = bytes_per_row / 4
        for i in range(pixels_per_row):
            for j in range(pixel_rows):
                little = j
                little_mid = j + pixel_rows
                big_mid = j + (2 * pixel_rows)
                big = j + (3 * pixel_rows)
                pixels[j::pixel_rows,i] = bits[big::bytes_per_row,i] * 8 + bits[big_mid::bytes_per_row,i] * 4 + bits[little_mid::bytes_per_row,i] * 2 + bits[little::bytes_per_row,i]


class FourBitPlanesLineBE(FourBitPlanesLE):
    name = "4 Bit Planes (big endian, interleave by line)"

    def get_bitplane_pixels(self, bits, pixels, bytes_per_row, pixels_per_row):
        pixel_rows = bytes_per_row / 4
        for i in range(pixels_per_row):
            for j in range(pixel_rows):
                little = j + (3 * pixel_rows)
                little_mid = j + (2 * pixel_rows)
                big_mid = j + pixel_rows
                big = j
                pixels[j::pixel_rows,i] = bits[big::bytes_per_row,i] * 8 + bits[big_mid::bytes_per_row,i] * 4 + bits[little_mid::bytes_per_row,i] * 2 + bits[little::bytes_per_row,i]


class GTIA9(FourBitsPerPixel):
    name = "GTIA 9 (4bpp, 16 luminances, 1 color)"
    scale_width = 4
    pixels_per_byte = 2

    def get_antic_color_registers(self, segment_viewer):
        first_color = segment_viewer.machine.antic_color_registers[8] & 0xf0
        return range(first_color, first_color + 16)

    def get_colors(self, segment_viewer, registers):
        antic_color_registers = self.get_antic_color_registers(segment_viewer)
        color_registers = segment_viewer.machine.get_color_registers(antic_color_registers)
        h_colors = colors.get_blended_color_registers(color_registers, segment_viewer.preferences.highlight_background_color)
        m_colors = colors.get_blended_color_registers(color_registers, segment_viewer.preferences.match_background_color)
        c_colors = colors.get_blended_color_registers(color_registers, segment_viewer.preferences.comment_background_color)
        d_colors = colors.get_dimmed_color_registers(color_registers, segment_viewer.preferences.background_color, segment_viewer.preferences.data_background_color)
        return color_registers, h_colors, m_colors, c_colors, d_colors


class GTIA10(GTIA9):
    name = "GTIA 10 (4bpp, 9 colors)"

    def get_antic_color_registers(self, segment_viewer):
        return list(segment_viewer.machine.antic_color_registers[0:9]) + [0] * 7


class GTIA11(GTIA9):
    name = "GTIA 11 (4bpp, 1 luminace, 16 colors)"

    def get_antic_color_registers(self, segment_viewer):
        first_color = segment_viewer.machine.antic_color_registers[8] & 0x0f
        return range(first_color, first_color + 256, 16)


class BaseBytePerPixelRenderer(BaseRenderer):
    """A generic renderer to display one pixel of the source using a byte
    for the image. This provides highlighting on a per-pixel level which isn't possible with modes that have multiple pixels in a byte. This is used as an intermediate renderer, so the image format can convert to byte per pixel, and this renderer can display it.

    Theoretically this will be able to display 256 colors, but at the
    moment only uses the first 16 colors. It is mapped to the ANTIC color
    register order, so the first 4 colors are player colors, then the 5
    playfield colors. A blank screen corresponds to the index value of 8, so
    the last playfield color.
    """
    name = "Intermediate Mode 1 Byte Per Pixel"
    pixels_per_byte = 1
    bitplanes = 1

    def pixels_from_2bpp(self, segment_viewer, bytes_per_row, nr, count, bytes, style, colors):
        bits = np.unpackbits(bytes)
        bits = bits.reshape((-1, 8))
        pixels = np.empty((nr * bytes_per_row, 4), dtype=np.uint8)
        pixels[:,0] = bits[:,0] * 2 + bits[:,1]
        pixels[:,1] = bits[:,2] * 2 + bits[:,3]
        pixels[:,2] = bits[:,4] * 2 + bits[:,5]
        pixels[:,3] = bits[:,6] * 2 + bits[:,7]
        style_per_pixel = np.vstack((style, style, style, style)).T
        return pixels, style_per_pixel

    def get_image(self, segment_viewer, bytes_per_row, nr, count, bytes, style):
        normal = style == 0
        highlight = (style & selected_bit_mask) == selected_bit_mask
        comment = (style & comment_bit_mask) == comment_bit_mask
        data = (style & user_bit_mask) > 0
        match = (style & match_bit_mask) == match_bit_mask

        color_registers, h_colors, m_colors, c_colors, d_colors = self.get_colors(segment_viewer, range(16))
        bitimage = np.empty((nr * bytes_per_row, 3), dtype=np.uint8)
        for i in range(16):
            color_is_set = (bytes == i)
            bitimage[color_is_set & normal] = color_registers[i]
            bitimage[color_is_set & comment] = c_colors[i]
            bitimage[color_is_set & match] = m_colors[i]
            bitimage[color_is_set & data] = d_colors[i]
            bitimage[color_is_set & highlight] = h_colors[i]
        bitimage[count:,:] = segment_viewer.preferences.empty_background_color.Get(False)
        return bitimage.reshape((nr, bytes_per_row, 3))


def get_numpy_font_map_image(segment_viewer, antic_font, bytes, style, start_byte, end_byte, bytes_per_row, num_rows, start_col, num_cols):
    width = int(antic_font.char_w * num_cols)
    height = int(num_rows * antic_font.char_h)
    log.debug("pixel width: %dx%d" % (width, height))
    array = np.empty((height, width, 3), dtype=np.uint8)

    log.debug("start byte: %s, end_byte: %s, bytes_per_row=%d num_rows=%d start_col=%d num_cols=%d" % (start_byte, end_byte, bytes_per_row, num_rows, start_col, num_cols))
    end_col = min(bytes_per_row, start_col + num_cols)
    y = 0
    e = start_byte
    f = antic_font.normal_font
    fh = antic_font.highlight_font
    fd = antic_font.data_font
    fm = antic_font.match_font
    fc = antic_font.comment_font
    char_w = antic_font.char_w
    char_h = antic_font.char_h
    mapping = segment_viewer.machine.font_mapping.font_mapping
    for j in range(num_rows):
        x = 0
        for i in range(start_col, start_col + num_cols):
            if e + i >= end_byte or i >= end_col:
                array[y:y+char_h,x:x+char_w,:] = segment_viewer.preferences.background_color
            else:
                c = mapping[bytes[j, i]]
                s = style[j, i]
                if s & selected_bit_mask:
                    array[y:y+char_h,x:x+char_w,:] = fh[c]
                elif s & match_bit_mask:
                    array[y:y+char_h,x:x+char_w,:] = fm[c]
                elif s & comment_bit_mask:
                    array[y:y+char_h,x:x+char_w,:] = fc[c]
                elif s & user_bit_mask:
                    array[y:y+char_h,x:x+char_w,:] = fd[c]
                else:
                    array[y:y+char_h,x:x+char_w,:] = f[c]
            x += char_w
        y += char_h
        e += bytes_per_row
    return array


class Mode2(BaseRenderer):
    name = "Antic 2 (Gr 0)"
    char_bit_width = 8
    char_bit_height = 8
    scale_width = 1
    scale_height = 1
    expected_chars = 128

    @classmethod
    def get_image(cls, machine, antic_font, bytes, style, start_byte, end_byte, bytes_per_row, nr, start_col, visible_cols):
        if speedups is not None:
            array = speedups.get_numpy_font_map_image(machine, antic_font, bytes, style, start_byte, end_byte, bytes_per_row, nr, start_col, visible_cols)
        else:
            array = get_numpy_font_map_image(machine, antic_font, bytes, style, start_byte, end_byte, bytes_per_row, nr, start_col, visible_cols)
        return array

    @property
    def bytes_per_char(self):
        return (self.char_bit_width + 7) // 8 * self.char_bit_height

    def get_font(self, data, colors, gr0_colors, reverse=False):
        bits = self.data_to_bits(data)
        font = self.bits_to_font(bits, colors, gr0_colors, reverse)
        return font

    def data_to_bits(self, data):
        """Convert byte data into bits, returning only a subset if
        required
        """
        padded = self.pad_data(data)
        bits = np.unpackbits(padded)
        bits = bits.reshape((-1, 8, 8))
        bits = self.select_subset(bits)
        return bits

    def pad_data(self, data):
        """Expand (or shrink if necessary) to conform to the expected input
        size of font data array
        """
        count = data.shape[0]
        expected_bytes = self.bytes_per_char * self.expected_chars
        if count > expected_bytes:
            data = data[0:expected_bytes]
        elif count < expected_bytes:
            expanded = np.zeros((expected_bytes), dtype=np.uint8)
            expanded[0:count] = data
            expanded[count:] = 0
            data = expanded
        return data

    def select_subset(self, bits):
        """If the font is made up of only a portion of the data, return the
        array that contains only the interesting bits.
        """
        return bits

    def bits_to_font(self, bits, colors, gr0_colors, reverse=False):
        fg, bg = gr0_colors
        if reverse:
            fg, bg = bg, fg
        r = np.empty(bits.shape, dtype=np.uint8)
        r[bits==0] = bg[0]
        r[bits==1] = fg[0]
        g = np.empty(bits.shape, dtype=np.uint8)
        g[bits==0] = bg[1]
        g[bits==1] = fg[1]
        b = np.empty(bits.shape, dtype=np.uint8)
        b[bits==0] = bg[2]
        b[bits==1] = fg[2]
        font = np.zeros((256, 8, 8, 3), dtype=np.uint8)
        # store the first 128 chars as the normal chars
        font[0:128,:,:,0] = r
        font[0:128,:,:,1] = g
        font[0:128,:,:,2] = b

        # create inverse characters from first 128 chars
        r[bits==0] = fg[0]
        r[bits==1] = bg[0]
        g[bits==0] = fg[1]
        g[bits==1] = bg[1]
        b[bits==0] = fg[2]
        b[bits==1] = bg[2]
        font[128:256,:,:,0] = r
        font[128:256,:,:,1] = g
        font[128:256,:,:,2] = b
        return font


class Mode4(Mode2):
    name = "Antic 4 (40x24, 5 color)"

    def bits_to_font(self, bits, colors, gr0_colors, reverse=False):
        """ http://www.atarimagazines.com/compute/issue49/419_1_Graphics_0_Text_In_Four_Colors.php
        
        There are four possible combinations of two bits: 00, 01, 10, 11. Each combination represents a different color. The color corresponding to the bit-pair 00 is stored at location 712; the color for the bit-pair 01 is at location 708; the color for bit-pair 10 is at 709; the color for bit-pair 11 is at 710.
        """
        pf0, pf1, pf2, pf3, bak = colors[4:9]
        r = np.empty(bits.shape, dtype=np.uint8)
        g = np.empty(bits.shape, dtype=np.uint8)
        b = np.empty(bits.shape, dtype=np.uint8)

        c = np.empty((128, 8, 4), dtype=np.uint8)
        c[:,:,0] = bits[:,:,0]*2 + bits[:,:,1]
        c[:,:,1] = bits[:,:,2]*2 + bits[:,:,3]
        c[:,:,2] = bits[:,:,4]*2 + bits[:,:,5]
        c[:,:,3] = bits[:,:,6]*2 + bits[:,:,7]

        pixels = np.empty((128, 8, 4, 3), dtype=np.uint8)
        pixels[c==0] = bak
        pixels[c==1] = pf0
        pixels[c==2] = pf1
        pixels[c==3] = pf2

        font = np.zeros((256, 8, 4, 3), dtype=np.uint8)
        font[0:128,:,:,:] = pixels

        # Inverse characters use pf3 in place of pf2
        pixels[c==3] = pf3
        font[128:256,:,:,:] = pixels

        # create a double-width image to expand the pixels to the correct
        # aspect ratio
        output = intwscale_font(font, 2)
        return output


class Mode5(Mode4):
    name = "Antic 5 (40x12, 5 color)"
    scale_height = 2


class Mode6Base(Mode2):
    name = "Antic 6 (base class)"
    scale_width = 2

    def bits_to_font(self, bits, colors, gr0_colors, reverse=False):
        bg = colors[8]
        r = np.empty(bits.shape, dtype=np.uint8)
        g = np.empty(bits.shape, dtype=np.uint8)
        b = np.empty(bits.shape, dtype=np.uint8)
        font = np.zeros((256, 8, 8, 3), dtype=np.uint8)

        start_char = 0
        for i in range(4, 8):
            end_char = start_char + 64
            fg = colors[i]
            r[bits==0] = bg[0]
            r[bits==1] = fg[0]
            g[bits==0] = bg[1]
            g[bits==1] = fg[1]
            b[bits==0] = bg[2]
            b[bits==1] = fg[2]
            font[start_char:end_char,:,:,0] = r
            font[start_char:end_char,:,:,1] = g
            font[start_char:end_char,:,:,2] = b
            start_char = end_char
        return font


class Mode6Upper(Mode6Base):
    name = "Antic 6 (Gr 1) Uppercase and Numbers"

    def select_subset(self, bits):
        return bits[0:64,:,:]


class Mode6Lower(Mode6Base):
    name = "Antic 6 (Gr 1) Lowercase and Symbols"

    def select_subset(self, bits):
        return bits[64:128,:,:]


class Mode7Upper(Mode6Base):
    name = "Antic 7 (Gr 2) Uppercase and Numbers"
    scale_height = 2

    def select_subset(self, bits):
        return bits[0:64,:,:]


class Mode7Lower(Mode6Base):
    name = "Antic 7 (Gr 2) Lowercase and Symbols"
    scale_height = 2

    def select_subset(self, bits):
        return bits[64:128,:,:]


class Apple2TextMode(Mode2):
    name = "Apple ]["
    char_bit_width = 7
    expected_chars = 256

    def pad_data(self, data):
        """Expand (or shrink if necessary) to conform to the expected input
        size of font data array
        """
        count = data.shape[0]

        # if more than 128 characters, assume not blinking and pad/truncate to
        # 256 chars
        if count >= 2048:
            return data[0:2048]
        if count > 1024:
            expanded = np.zeros(2048, dtype=np.uint8)
            expanded[0:count] = data
            expanded[count:] = 0
            return expanded

        # pad to 1024 if necessary; inverse/blinking will be applied later
        if count < 1024:
            expanded = np.zeros(1024, dtype=np.uint8)
            expanded[0:count] = data
            expanded[count:] = 0
            data = expanded
        return data

    def bits_to_font(self, bits, colors, gr0_colors, reverse=False):
        bg = (0, 0, 0)
        fg = (255, 255, 255)
        r = np.empty(bits.shape, dtype=np.uint8)
        r[bits==0] = bg[0]
        r[bits==1] = fg[0]
        g = np.empty(bits.shape, dtype=np.uint8)
        g[bits==0] = bg[1]
        g[bits==1] = fg[1]
        b = np.empty(bits.shape, dtype=np.uint8)
        b[bits==0] = bg[2]
        b[bits==1] = fg[2]
        font = np.zeros((256, 8, 7, 3), dtype=np.uint8)
        if bits.shape[0] == 256:
            # all 256 chars are defined, so just store them
            font[:,:,:,0] = r[:,:,8:0:-1]
            font[:,:,:,1] = g[:,:,8:0:-1]
            font[:,:,:,2] = b[:,:,8:0:-1]
        else:
            # only 128 chars are present, so create inversed/blink copies

            # Normal characters get stored in 2nd 128 char positions
            font[128:256,:,:,0] = r[:,:,8:0:-1]
            font[128:256,:,:,1] = g[:,:,8:0:-1]
            font[128:256,:,:,2] = b[:,:,8:0:-1]

            # First 64 are inversed
            r[bits==0] = fg[0]
            r[bits==1] = bg[0]
            g[bits==0] = fg[1]
            g[bits==1] = bg[1]
            b[bits==0] = fg[2]
            b[bits==1] = bg[2]
            font[0:64,:,:,0] = r[0:64,:,8:0:-1]
            font[0:64,:,:,1] = g[0:64,:,8:0:-1]
            font[0:64,:,:,2] = b[0:64,:,8:0:-1]

            # Next 64 are blinking!
            if reverse:
                fg, bg = bg, fg
            r[bits==0] = fg[0]
            r[bits==1] = bg[0]
            g[bits==0] = fg[1]
            g[bits==1] = bg[1]
            b[bits==0] = fg[2]
            b[bits==1] = bg[2]
            font[64:128,:,:,0] = r[0:64,:,8:0:-1]
            font[64:128,:,:,1] = g[0:64,:,8:0:-1]
            font[64:128,:,:,2] = b[0:64,:,8:0:-1]
        return font


class ATASCIIFontMapping(object):
    name = "ASCII Order"
    font_mapping = atascii_to_internal

    def __eq__(self, other):
        try:
            return self.name == other.name
        except AttributeError:
            pass
        return False

    def wx_char_to_byte(self, char, mods, control):
        byte = None

        if mods == wx.MOD_RAW_CONTROL:
            if char == 44:  # Ctrl-, prints ATASCII 0 (heart)
                byte = 0 + control.inverse
            elif char >= 65 and char <= 90:  # Ctrl-[A-Z] prints ATASCII chars 1-26
                byte = char - 64 + control.inverse
            elif char == 46:  # Ctrl-. prints ATASCII 96 (diamond)
                byte = 96 + control.inverse
            elif char == 59:  # Ctrl-; prints ATASCII 123 (spade)
                byte = 123 + control.inverse
            elif char == wx.WXK_TAB:
                byte = 158
            elif char == 50:  # Ctrl-2 prints ATASCII 253 (buzzer)
                byte = 253
            elif char == wx.WXK_INSERT:
                byte = 255
        elif mods == wx.MOD_SHIFT:
            if char == wx.WXK_BACK:
                byte = 156
            elif char == wx.WXK_INSERT:
                byte = 157
            elif char == wx.WXK_TAB:
                byte = 159
        elif char == wx.WXK_HOME:
            byte = 125
        elif char == wx.WXK_BACK:
            byte = 126
        elif char == wx.WXK_TAB:
            byte = 127
        elif char == wx.WXK_RETURN:
            byte = 155
        elif char == wx.WXK_DELETE:
            byte = 254
        elif char == wx.WXK_INSERT:
            byte = 255

        elif control.pending_esc:
            if char == wx.WXK_ESCAPE:
                byte = 27
            elif char == wx.WXK_UP:
                byte = 28
            elif char == wx.WXK_DOWN:
                byte = 29
            elif char == wx.WXK_LEFT:
                byte = 30
            elif char == wx.WXK_RIGHT:
                byte = 31

        elif char == wx.WXK_ESCAPE:
            control.pending_esc = True

        return byte

    def convert_byte_mapping(self, char):
        return char


class AnticFontMapping(ATASCIIFontMapping):
    name = "Antic Order"
    font_mapping = np.arange(256, dtype=np.uint8)

    def convert_byte_mapping(self, char):
        try:
            char = atascii_to_internal[char]
        except IndexError:
            pass
        return char


class BytePerPixelMemoryMap(BaseRenderer):
    name = "1Bpp Greyscale"

    def get_image(self, segment_viewer, bytes, style, start_byte, end_byte, bytes_per_row, nr, start_col, visible_cols):
        if speedups is not None:
            array = speedups.get_numpy_memory_map_image(segment_viewer, bytes, style, start_byte, end_byte, bytes_per_row, nr, start_col, visible_cols)
        else:
            array = get_numpy_memory_map_image(segment_viewer, bytes, style, start_byte, end_byte, bytes_per_row, nr, start_col, visible_cols)
        return array


def get_numpy_memory_map_image(segment_viewer, bytes, style, start_byte, end_byte, bytes_per_row, num_rows, start_col, num_cols):
    log.debug("SLOW VERSION OF get_numpy_memory_map_image!!!")
    num_rows_with_data = (end_byte - start_byte + bytes_per_row - 1) / bytes_per_row

    log.debug(str([end_byte, start_byte, (end_byte - start_byte) / bytes_per_row]))
    end_row = min(num_rows_with_data, num_rows)
    end_col = min(bytes_per_row, start_col + num_cols)

    width = end_col - start_col
    height = num_rows_with_data
    log.debug("memory map size: %dx%d, rows with data=%d, rows %d, cols %d-%d" % (width, height, num_rows_with_data, num_rows, start_col, start_col + width - 1))
    array = np.empty((height, width, 3), dtype=np.uint8)
    array[:,:] = segment_viewer.preferences.empty_background_color.Get(False)
    selected_color = segment_viewer.preferences.highlight_background_color

    y = 0
    e = start_byte
    for j in range(end_row):
        x = 0
        for i in range(start_col, end_col):
            if e + i >= end_byte:
                break
            c = bytes[j, i] ^ 0xff
            s = style[j, i]
            if s & selected_bit_mask:
                r = selected_color[0] * c >> 8
                g = selected_color[1] * c >> 8
                b = selected_color[2] * c >> 8
                array[y,x,:] = (r, g, b)
            else:
                array[y,x,:] = (c, c, c)
            x += 1
        y += 1
        e += bytes_per_row
    return array
