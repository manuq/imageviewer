# Copyright (C) 2008, One Laptop per Child
# Author: Sayamindu Dasgupta <sayamindu@laptop.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import logging
import cairo
import math

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GObject

ZOOM_STEP = 0.05
ZOOM_MAX = 4
ZOOM_MIN = 0.05


def _surface_from_file(file_location, ctx):
    pixbuf = GdkPixbuf.Pixbuf.new_from_file(file_location)
    surface = ctx.get_target().create_similar(
        cairo.CONTENT_COLOR_ALPHA, pixbuf.get_width(),
        pixbuf.get_height())

    ctx_surface = cairo.Context(surface)
    Gdk.cairo_set_source_pixbuf(ctx_surface, pixbuf, 0, 0)
    ctx_surface.paint()
    return surface

def _rotate_surface(surface, direction):
    ctx = cairo.Context(surface)
    new_surface = ctx.get_target().create_similar(
        cairo.CONTENT_COLOR_ALPHA, surface.get_height(),
        surface.get_width())

    ctx_surface = cairo.Context(new_surface)

    if direction == 1:
        ctx_surface.translate(surface.get_height(), 0)
    else:
        ctx_surface.translate(0, surface.get_width())

    ctx_surface.rotate(math.pi / 2 * direction)

    ctx_surface.set_source_surface(surface, 0, 0)
    ctx_surface.paint()

    return new_surface

class ImageViewer(Gtk.DrawingArea):
    def __init__(self):
        Gtk.DrawingArea.__init__(self)

        self._file_location = None
        self._surface = None
        self._zoom = None
        self._target_point = None
        self._anchor_point = None

        self._in_dragtouch = False
        self._in_zoomtouch = False
        self._zoomtouch_scale = 1

        self.connect('draw', self.__draw_cb)

    def set_file_location(self, file_location):
        self._file_location = file_location
        self.queue_draw()

    def _center_target_point(self):
        alloc = self.get_parent().get_allocation()
        self._target_point = (alloc.width / 2, alloc.height / 2)

    def _center_anchor_point(self):
        self._anchor_point = (self._surface.get_width() / 2,
                              self._surface.get_height() / 2)

    def _center_if_small(self):
        # If at the current size the image surface is smaller than the
        # available space, center it on the canvas.

        alloc = self.get_parent().get_allocation()

        scaled_width = self._surface.get_width() * self._zoom
        scaled_height = self._surface.get_height() * self._zoom

        if alloc.width >= scaled_width and alloc.height >= scaled_height:
            self._center_target_point()
            self._center_anchor_point()
            self.queue_draw()

    def _do_set_zoom(self, zoom):
        self._zoom = zoom

        # Update size and scroll window
        width = int(self._surface.get_width() * self._zoom)
        height = int(self._surface.get_height() * self._zoom)
        self.set_size_request(width, height)

    def set_zoom(self, zoom):
        if zoom < ZOOM_MIN or zoom > ZOOM_MAX:
            return
        self._do_set_zoom(zoom)

    def get_zoom(self):
        return self._zoom

    def can_zoom_in(self):
        return self._zoom + ZOOM_STEP < ZOOM_MAX

    def can_zoom_out(self):
        return self._zoom - ZOOM_STEP > ZOOM_MIN

    def zoom_in(self):
        if not self.can_zoom_in():
            return
        self._do_set_zoom(self._zoom + ZOOM_STEP)

    def zoom_out(self):
        if not self.can_zoom_out():
            return
        self._do_set_zoom(self._zoom - ZOOM_STEP)
        self._center_if_small()

    def zoom_to_fit(self):
        # This tries to figure out a best fit model
        # If the image can fit in, we show it in 1:1,
        # in any other case we show it in a fit to screen way

        alloc = self.get_parent().get_allocation()

        surface_width = self._surface.get_width()
        surface_height = self._surface.get_height()

        zoom = None
        if alloc.width < surface_width or alloc.height < surface_height:
            # Image is larger than allocated size
            zoom = min(alloc.width * 1.0 / surface_width,
                       alloc.height * 1.0 / surface_height)
        else:
            zoom = 1.0
        self._do_set_zoom(zoom)
        self._center_target_point()
        self._center_anchor_point()
        self.queue_draw()

    def zoom_original(self):
        self._do_set_zoom(1)
        self._center_if_small()

    def start_dragtouch(self, coords):
        self._in_dragtouch = True

        prev_target_point = self._target_point

        # Set target point to the relative coordinates of this view.
        alloc = self.get_parent().get_allocation()
        self._target_point = (coords[1], coords[2])

        # Calculate the new anchor point.

        prev_anchor_scaled = (self._anchor_point[0] * self._zoom,
                              self._anchor_point[1] * self._zoom)

        # This vector is the top left coordinate of the scaled image.
        scaled_image_topleft = (prev_target_point[0] - prev_anchor_scaled[0],
                                prev_target_point[1] - prev_anchor_scaled[1])

        anchor_scaled = (self._target_point[0] - scaled_image_topleft[0],
                         self._target_point[1] - scaled_image_topleft[1])

        self._anchor_point = (int(anchor_scaled[0] * 1.0 / self._zoom),
                              int(anchor_scaled[1] * 1.0 / self._zoom))

        self.queue_draw()

    def update_dragtouch(self, coords):
        # Drag touch will be replaced by zoom touch if another finger
        # is placed over the display.  When the user finishes zoom
        # touch, it will probably remove one finger after the other,
        # and this method will be called.  In that probable case, we
        # need to start drag touch again.
        if not self._in_dragtouch:
            self.start_dragtouch(coords)
            return

        self._target_point = (coords[1], coords[2])
        self.queue_draw()

    def finish_dragtouch(self, coords):
        self._in_dragtouch = False
        self._center_if_small()

    def start_zoomtouch(self, center):
        self._in_zoomtouch = True
        self._zoomtouch_scale = 1

        # Zoom touch replaces drag touch.
        self._in_dragtouch = False

        prev_target_point = self._target_point

        # Set target point to the relative coordinates of this view.
        alloc = self.get_parent().get_allocation()
        self._target_point = (center[1] - alloc.x, center[2] - alloc.y)

        # Calculate the new anchor point.

        prev_anchor_scaled = (self._anchor_point[0] * self._zoom,
                              self._anchor_point[1] * self._zoom)

        # This vector is the top left coordinate of the scaled image.
        scaled_image_topleft = (prev_target_point[0] - prev_anchor_scaled[0],
                                prev_target_point[1] - prev_anchor_scaled[1])

        anchor_scaled = (self._target_point[0] - scaled_image_topleft[0],
                         self._target_point[1] - scaled_image_topleft[1])

        self._anchor_point = (int(anchor_scaled[0] * 1.0 / self._zoom),
                              int(anchor_scaled[1] * 1.0 / self._zoom))

        self.queue_draw()

    def update_zoomtouch(self, center, scale):
        self._zoomtouch_scale = scale

        # Set target point to the relative coordinates of this view.
        alloc = self.get_parent().get_allocation()
        self._target_point = (center[1] - alloc.x, center[2] - alloc.y)

        self.queue_draw()

    def finish_zoomtouch(self):
        self._in_zoomtouch = False

        # Apply zoom
        zoom = self._zoom * self._zoomtouch_scale
        self._zoomtouch_scale = 1

        # Restrict zoom values
        if zoom < ZOOM_MIN:
            zoom = ZOOM_MIN
        elif zoom > ZOOM_MAX:
            zoom = ZOOM_MAX

        self._do_set_zoom(zoom)
        self._center_if_small()

    def rotate_anticlockwise(self):
        self._surface = _rotate_surface(self._surface, -1)

        # Recalculate the anchor point to make it relative to the new
        # top left corner.
        self._anchor_point = (
            self._anchor_point[1],
            self._surface.get_height() - self._anchor_point[0])

        self.queue_draw()

    def rotate_clockwise(self):
        self._surface = _rotate_surface(self._surface, 1)

        # Recalculate the anchor point to make it relative to the new
        # top left corner.
        self._anchor_point = (
            self._surface.get_width() - self._anchor_point[1],
            self._anchor_point[0])

        self.queue_draw()

    def __draw_cb(self, widget, ctx):

        # If the image surface is not set, it reads it from the file
        # location.  If the file location is not set yet, it just
        # returns.
        if self._surface is None:
            if self._file_location is None:
                return
            self._surface = _surface_from_file(self._file_location, ctx)

        if self._zoom is None:
            self.zoom_to_fit()

        # If no target point was set via pinch-to-zoom, default to the
        # center of the screen.
        if self._target_point is None:
            self._center_target_point()

        # If no anchor point was set via pinch-to-zoom, default to the
        # center of the surface.
        if self._anchor_point is None:
            self._center_anchor_point()

        ctx.translate(*self._target_point)

        zoom_absolute = self._zoom * self._zoomtouch_scale
        ctx.scale(zoom_absolute, zoom_absolute)

        ctx.translate(self._anchor_point[0] * -1, self._anchor_point[1] * -1)

        ctx.set_source_surface(self._surface, 0, 0)

        if self._in_zoomtouch or self._in_dragtouch:
            ctx.get_source().set_filter(cairo.FILTER_NEAREST)

        ctx.paint()
