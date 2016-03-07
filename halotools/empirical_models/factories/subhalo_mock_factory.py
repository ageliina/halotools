# -*- coding: utf-8 -*-
"""
Module used to construct mock galaxy populations 
based on models that populate subhalos. 

"""

import numpy as np
from copy import copy 

from astropy.table import Table 

from .mock_factory_template import MockFactory

from .. import model_helpers, model_defaults
from ...custom_exceptions import *


__all__ = ['SubhaloMockFactory']
__author__ = ['Andrew Hearin']

unavailable_haloprop_msg = ("Your model requires that the ``%s`` key appear in the halo catalog,\n"
    "but this column is not available in the catalog you attempted to populate.\n")


class SubhaloMockFactory(MockFactory):
    """ Class responsible for populating a simulation with a 
    population of mock galaxies based on models generated by 
    `~halotools.empirical_models.SubhaloModelFactory`. 

    """

    def __init__(self, **kwargs):
        """
        Parameters 
        ----------
        halocat : object, keyword argument 
            Object containing the halo catalog and other associated data.  
            Produced by `~halotools.sim_manager.CachedHaloCatalog`

        model : object, keyword argument
            A model built by a sub-class of `~halotools.empirical_models.SubhaloModelFactory`. 

        populate : boolean, optional   
            If set to ``False``, the class will perform all pre-processing tasks 
            but will not call the ``model`` to populate the ``galaxy_table`` 
            with mock galaxies and their observable properties. Default is ``True``. 
        """

        MockFactory.__init__(self, **kwargs)
        halocat = kwargs['halocat']

        # Pre-compute any additional halo properties required by the model
        self.preprocess_halo_catalog(halocat)
        self.precompute_galprops()

    def preprocess_halo_catalog(self, halocat):
        """ Method to pre-process a halo catalog upon instantiation of the mock object. 

        New columns are added to the ``halo_table`` according to any entries in the 
        ``new_haloprop_func_dict``. 

        See also 
        ---------
        :ref:`new_haloprop_func_dict_mechanism`

        """
        halo_table = halocat.halo_table

        if ( ('halo_hostid' not in self.additional_haloprops) & ('halo_hostid' in halo_table.keys()) ):
            self.additional_haloprops.append('halo_hostid')

        if ( ('halo_mvir_host_halo' not in self.additional_haloprops) & 
            ('halo_mvir_host_halo' in halo_table.keys()) ):
            self.additional_haloprops.append('halo_mvir_host_halo')

        ### Create new columns of the halo catalog, if applicable
        try:
            d = self.model.new_haloprop_func_dict
            for new_haloprop_key, new_haloprop_func in d.iteritems():
                halo_table[new_haloprop_key] = new_haloprop_func(table = halo_table)
                self.additional_haloprops.append(new_haloprop_key)
        except AttributeError:
            pass

        self.halo_table = Table()
        for key in self.additional_haloprops:
            try:
                self.halo_table[key] = halo_table[key]
            except KeyError:
                raise HalotoolsError(unavailable_haloprop_msg % key)


    def precompute_galprops(self):
        """ Method pre-processes the input subhalo catalog, and pre-computes 
        all halo properties that will be inherited by the ``galaxy_table``. 

        For example, in subhalo-based models, the phase space coordinates of the 
        galaxies are hard-wired to be equal to the phase space coordinates of the 
        parent subhalos, so these keys of the galaxy_table 
        can be pre-computed once and for all. 

        Additionally, a feature of some composite models may have explicit dependence 
        upon the type of halo/galaxy. The `gal_type_func` mechanism addresses this potential need 
        by adding an additional column(s) to the galaxy_table. These additional columns 
        can also be pre-computed as halo types do not depend upon model parameter values. 
        """

        self._precomputed_galprop_list = []

        for key in self.additional_haloprops:
            self.galaxy_table[key] = self.halo_table[key]
            self._precomputed_galprop_list.append(key)

        phase_space_keys = ['x', 'y', 'z', 'vx', 'vy', 'vz']
        for newkey in phase_space_keys:
            self.galaxy_table[newkey] = self.galaxy_table[model_defaults.host_haloprop_prefix+newkey]
            self._precomputed_galprop_list.append(newkey)

        self.galaxy_table['galid'] = np.arange(len(self.galaxy_table))
        self._precomputed_galprop_list.append('galid')

        # Component models may explicitly distinguish between certain types of halos, 
        # e.g., subhalos vs. host halos. Since this assignment is not dynamic, 
        # it can be pre-computed. 
        for feature, component_model in self.model.model_dictionary.iteritems():

            try:
                f = component_model.gal_type_func
                newkey = feature + '_gal_type'
                self.galaxy_table[newkey] = f(table=self.galaxy_table)
                self._precomputed_galprop_list.append(newkey)
            except AttributeError:
                pass
            except:
                clname = component_model.__class__.__name__
                msg = ("\nThe `gal_type_func` attribute of the " + clname + 
                    "\nraises an unexpected exception when passed a halo table as a "
                    "table keyword argument. \n"
                    "If the features in your component model have explicit dependence "
                    "on galaxy type, \nthen you must implement the `gal_type_func` mechanism "
                    "in such a way that\nthis function accepts a "
                    "length-N halo table as a ``table`` keyword argument, \n"
                    "and returns a length-N array of strings.\n")
                raise HalotoolsError(msg)

    def populate(self):
        """ Method populating subhalos with mock galaxies. 

        Each method appearing in the ``_mock_generation_calling_sequence`` attribute 
        of the composite model is called in sequence, always being passed the 
        ``galaxy_table`` as the ``table`` argument. 
        """
        self._allocate_memory()

        for method in self.model._mock_generation_calling_sequence:
            func = getattr(self.model, method)
            func(table = self.galaxy_table)

        if hasattr(self.model, 'galaxy_selection_func'):
            mask = self.model.galaxy_selection_func(self.galaxy_table)
            self.galaxy_table = self.galaxy_table[mask]

    def _allocate_memory(self):
        """
        """
        Ngals = len(self.galaxy_table)

        new_column_generator = (key for key in self.model._galprop_dtypes_to_allocate.names 
            if key not in self._precomputed_galprop_list)

        for key in new_column_generator:
            dt = self.model._galprop_dtypes_to_allocate[key]
            self.galaxy_table[key] = np.empty(Ngals, dtype = dt)







