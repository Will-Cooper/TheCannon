from __future__ import (absolute_import, division, print_function)
import numpy as np
import matplotlib.pyplot as plt
from .helpers.triangle import corner

import sys

PY3 = sys.version_info[0] > 2

if PY3:
    basestring = (str, bytes)
else:
    basestring = (str, unicode)


class Dataset(object):
    """A class to represent a Dataset of stellar spectra and labels.

    Attributes
    ----------
    label_vals: numpy ndarray of shape (nstars, nlabels)
    SNRs: numpy ndarray of shape (nstars)
    lams: numpy ndarray of shape (nstars, npixels)
    fluxes: numpy ndarray of shape (nstars, npixels)
    ivars: numpy ndarray of shape (nstars, npixels)
    label_names: (optional) list of strings of length (nlabels)
    """

    def __init__(self, label_vals, SNRs, lams, fluxes, ivars,
                 label_names=None, label_names_tex=None):
        self.data = label_vals
        self.label_names = label_names
        self.data.add_column('SNRs', SNRs)
        self.lams = lams
        self.fluxes = fluxes
        self.ivars = ivars
        self.reset_label_vals()

    def reset_label_vals(self):
        self._label_vals = None

    def set_label_vals(self, vals):
        """ Set label vals from an array """
        self._label_vals = vals

    def set_label_names_tex(self, names):
        self.label_names_tex = names

    @property
    def IDs(self):
        return self.data['id']

    @property
    def SNRs(self):
        return self.data['SNRs']

    def get_plotting_labels(self):
        if self.label_names_tex is None:
            return self.label_names
        return self.label_names_tex
    
    def choose_labels(self, cols):
        """Updates the label_names and label_vals properties

        Parameters
        ----------
        cols: list of column indices corresponding to which to keep
        """
        self.label_names = []
        for k in cols:
            key = self.data.resolve_alias(k)
            if key not in self.data:
                raise KeyError('Attribute {0:s} not found'.format(key))
            else:
                self.label_names.append(key)

    def choose_objects(self, mask):
        """Updates the ID, spectra, label_vals properties to the subset that
        fits the mask

        Parameters
        ----------
        mask: ndarray or str
            boolean array where False means discard
            or str giving the condition on the label data table.
        """
        if type(mask) in basestring:
            _m = self.data.where(mask)
        else:
            _m = mask
        self.data = self.data.select('*', indices=_m)
        self.fluxes = self.fluxes[_m]
        self.ivars = self.ivars[_m]

    def label_triangle_plot(self, figname=None, labels=None):
        """Make a triangle plot for the selected labels

        Parameters
        ----------
        figname: str
            if provided, save the figure into the given file

        labels: sequence
            if provided, use this sequence as text labels for each label
            dimension
        """
        data = np.array([self.data[k] for k in self.label_names]).T
        labels = [r"$%s$" % l for l in self.get_plotting_labels()]
        print("Plotting every label against every other")
        fig = corner(data, labels=labels, show_titles=True,
                     title_args={"fontsize":12})
        if figname is not None:
            fig.savefig(figname)
            print("Saved fig %s" % figname)
            plt.close(fig)

    @property
    def label_vals(self):
        """ return the array of labels [nstars, nlabels] """
        if self._label_vals is None:
            return np.array([self.data[k] for k in self.label_names]).T
        else:
            return self._label_vals


def dataset_prediagnostics(reference_set, test_set,
                           SNR_plot_name = "SNRdist.png", 
                           triangle_plot_name = "reference_labels_triangle.png"):
    """ Plot SNR distributions and triangle plot of reference labels

    Parameters
    ----------
    reference_set: Dataset
        set used as training sample

    test_set: Dataset
        set for which labels are going to be inferred

    SNR_plot_name: string
        title of the saved SNR diagnostic plot
    
    triangle_plot_name: string
        title of the saved triangle plot for reference labels
    """
    print("Diagnostic for SNRs of reference and survey stars")
    plt.hist(reference_set.SNRs, alpha=0.5, label="Ref Stars")
    plt.hist(test_set.SNRs, alpha=0.5, label="Survey Stars")
    plt.legend(loc='upper right')
    plt.xscale('log')
    plt.title("SNR Comparison Between Reference & Test Stars")
    plt.xlabel("log(Formal SNR)")
    plt.ylabel("Number of Objects")
    plt.savefig(SNR_plot_name)
    plt.close()
    print("Saved fig %s" %SNR_plot_name)

    # Plot all reference labels against each other
    reference_set.label_triangle_plot(triangle_plot_name)


def dataset_postdiagnostics(reference_set, test_set,
                            triangle_plot_name = "survey_labels_triangle.png"):
    """ Run diagnostic tests on the test set after labels have been inferred.

    Tests result in the following output: one .txt file for each label listing
    all of the stars whose inferred labels lie >= 2 standard deviations outside
    the reference label space, a triangle plot showing all the survey labels 
    plotted against each other, and 1-to-1 plots for all of the labels showing
    how they compare to each other. 

    Parameters
    ----------
    reference_set: Dataset
        set used as training sample

    test_set: Dataset
        set for which labels are going to be inferred
    """
    # Find stars whose inferred labels lie outside the ref label space by 2-sig+
    label_names = reference_set.label_names
    nlabels = len(label_names)
    reference_labels = reference_set.label_vals
    test_labels = test_set.label_vals
    test_IDs = test_set.IDs
    mean = np.mean(reference_labels, 0)
    stdev = np.std(reference_labels, 0)
    lower = mean - 2 * stdev
    upper = mean + 2 * stdev
    for i in range(nlabels):
        label_name = label_names[i]
        test_vals = test_labels[:,i]
        warning = np.logical_or(test_vals < lower[i], test_vals > upper[i])
        filename = "flagged_stars_%s.txt" % i
        with open(filename, 'w') as output:
            for star in test_IDs[warning]:
                output.write('{0:s}\n'.format(star))
        print("Reference label %s" % label_name)
        print("flagged %s stars beyond 2-sig of reference labels" % sum(warning))
        print("Saved list %s" % filename)
    
    # Plot all survey labels against each other
    test_set.label_triangle_plot(triangle_plot_name)
    
    # 1-1 plots of all labels
    for i in range(nlabels):
        name = reference_set.get_plotting_labels()[i]
        orig = reference_labels[:,i]
        cannon = test_labels[:,i]
        low = np.minimum(min(orig), min(cannon))
        high = np.maximum(max(orig), max(cannon))
        fig, axarr = plt.subplots(2)
        ax1 = axarr[0]
        ax1.plot([low, high], [low, high], 'k-', linewidth=2.0, label="x=y")
        ax1.scatter(orig, cannon)
        ax1.legend()
        ax1.set_xlabel("Reference Value")
        ax1.set_ylabel("Cannon Output Value")
        ax1.set_title("1-1 Plot of Label " + r"$%s$" % name)
        ax2 = axarr[1]
        ax2.hist(cannon-orig)
        ax2.set_xlabel("Difference")
        ax2.set_ylabel("Count")
        ax2.set_title("Histogram of Output Minus Ref Labels")
        figname = "1to1_label_%s.png" % i
        plt.savefig(figname)
        print("Diagnostic for label output vs. input")
        print("Saved fig %s" % figname)
        plt.close()


class DataFrame(object):
    def __init__(self, spec_dir, label_file, contpix_file):
        self.spec_dir = spec_dir
        self.label_file = label_file
        self.contpix_file = contpix_file

    def get_spectra(self, *args, **kwags):
        raise NotImplemented('Derived classes need to implement this method')

    def get_reference_labels(self, *args, **kwags):
        raise NotImplemented('Derived classes need to implement this method')

    @property
    def dataset(self):
        if not hasattr(self, "_dataset"):
            self.load_dataset()
        return self._dataset

    def load_dataset(self, *args, **kwargs):
        print('Loading dataset... This may take a while')
        lambdas, norm_fluxes, norm_ivars, SNRs = self.get_spectra(*args, **kwargs)
        IDs, all_label_names, all_label_values = self.get_reference_labels()

        dataset = Dataset(all_label_values, SNRs, lambdas, norm_fluxes,
                          norm_ivars, all_label_names)

        self._dataset = dataset