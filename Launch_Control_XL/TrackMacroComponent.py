from __future__ import absolute_import, print_function, unicode_literals

class TrackMacroComponent(object):
    """
    Koppelt de 8 pan-encoders aan de Frequency parameter van de
    Auto Filter (DJ mode) op elke track.

    Gedrag:
    - Zoekt op naam 'Auto Filter' door alle devices op een track
    - Encoder passief als er geen Auto Filter op de track staat
    - Hermapt automatisch bij bank-scroll en device-wijzigingen
    """

    AUTO_FILTER_NAME = "Auto Filter"
    FREQUENCY_PARAM_NAME = "Frequency"

    def __init__(self, mixer, encoders, song, num_tracks=8):
        self._mixer = mixer
        self._encoders = encoders       # lijst van 8 encoder controls
        self._song = song
        self._num_tracks = num_tracks
        self._current_params = [None] * num_tracks
        self._track_listeners = {}      # id(track) -> (track, callback)

        self._update_all_mappings()

    # ─── Track ophalen ────────────────────────────────────────────────────────

    def _get_track(self, index):
        """Haal de Live track op, rekening houdend met bank-scroll offset."""
        try:
            offset = self._mixer.track_offset()
            tracks = self._song.visible_tracks
            track_index = offset + index
            if track_index < len(tracks):
                return tracks[track_index]
        except Exception:
            pass
        return None

    # ─── Auto Filter zoeken ───────────────────────────────────────────────────

    def _find_auto_filter(self, track):
        """
        Zoekt door alle devices op een track naar 'Auto Filter' op naam.
        Geeft het eerste gevonden device terug, anders None.
        """
        if track is None:
            return None

        for device in track.devices:
            if device.name == self.AUTO_FILTER_NAME:
                return device

        return None

    def _get_frequency_param(self, device):
        """
        Zoekt de Frequency parameter in de Auto Filter.
        Zoekt op naam zodat het robuust is tegen parameter-volgorde wijzigingen.
        """
        if device is None:
            return None

        for param in device.parameters:
            if param.name == self.FREQUENCY_PARAM_NAME:
                return param

        return None

    # ─── Encoder koppelen ─────────────────────────────────────────────────────

    def _map_encoder(self, index):
        """
        Koppelt encoder[index] aan de Frequency parameter van de Auto Filter
        op de bijbehorende track. Encoder is passief als er geen Auto Filter is.
        """
        encoder = self._encoders[index]
        if encoder is None:
            return

        # Zoek Auto Filter en Frequency parameter
        track = self._get_track(index)
        device = self._find_auto_filter(track)
        freq_param = self._get_frequency_param(device)

        # Ontkoppel de vorige parameter
        old_param = self._current_params[index]
        if old_param is not None:
            try:
                encoder.release_parameter()
            except Exception:
                pass

        self._current_params[index] = freq_param

        # Koppel aan Frequency (of None = encoder passief)
        if freq_param is not None:
            try:
                encoder.connect_to(freq_param)
            except Exception:
                pass

    def _update_all_mappings(self):
        """Hermap alle 8 encoders. Aanroepen bij init en na bank-scroll."""
        self._remove_device_listeners()
        for i in range(self._num_tracks):
            self._map_encoder(i)
            self._add_device_listener(i)

    # ─── Listeners ────────────────────────────────────────────────────────────

    def _add_device_listener(self, index):
        """
        Luistert naar device-wijzigingen op een track zodat de koppeling
        automatisch wordt bijgewerkt als een Auto Filter wordt toegevoegd
        of verwijderd.
        """
        track = self._get_track(index)
        if track is not None and id(track) not in self._track_listeners:
            callback = lambda idx=index: self._map_encoder(idx)
            track.add_devices_listener(callback)
            self._track_listeners[id(track)] = (track, callback)

    def _remove_device_listeners(self):
        """Verwijder alle actieve device-listeners netjes."""
        for track, callback in self._track_listeners.values():
            try:
                track.remove_devices_listener(callback)
            except Exception:
                pass
        self._track_listeners = {}

    # ─── Publieke methodes ────────────────────────────────────────────────────

    def on_track_offset_changed(self):
        """
        Aanroepen vanuit LaunchControlXL als de gebruiker de track-bank
        scrolt (bv. van tracks 1-8 naar tracks 9-16).
        """
        self._update_all_mappings()

    def disconnect(self):
        """Opruimen bij script-disconnect of herinitialisatie."""
        self._remove_device_listeners()
        for encoder in self._encoders:
            if encoder is not None:
                try:
                    encoder.release_parameter()
                except Exception:
                    pass
