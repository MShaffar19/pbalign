#!/usr/bin/env python
###############################################################################
# Copyright (c) 2011-2013, Pacific Biosciences of California, Inc.
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# * Redistributions of source code must retain the above copyright
#   notice, this list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
# * Neither the name of Pacific Biosciences nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# NO EXPRESS OR IMPLIED LICENSES TO ANY PARTY'S PATENT RIGHTS ARE GRANTED BY
# THIS LICENSE.  THIS SOFTWARE IS PROVIDED BY PACIFIC BIOSCIENCES AND ITS
# CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT
# NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
# PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL PACIFIC BIOSCIENCES OR
# ITS CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
# OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
# OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
# ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
###############################################################################

"""This script defines class PBAlignRunner.

PBAlignRunner uses AlignService to align PacBio reads in FASTA/BASE/PULSE/FOFN
formats to reference sequences, then uses FilterServices to filter out
alignments that do not satisfy filtering criteria, and finally generates a SAM
or BAM file.

"""

# Author: Yuan Li

import functools
import logging
import time
import sys
import shutil
from os import readlink

from pbcommand.cli import pbparser_runner
from pbcommand.utils import setup_log
from pbcore.util.ToolRunner import PBToolRunner
from pbcore.io import (AlignmentSet, ConsensusAlignmentSet)

from pbalign.__init__ import get_version
from pbalign.options import (ALGORITHM_CANDIDATES, get_contract_parser,
                             resolved_tool_contract_to_args)
from pbalign.alignservice.blasr import BlasrService
from pbalign.alignservice.bowtie import BowtieService
from pbalign.alignservice.gmap import GMAPService
from pbalign.utils.fileutil import getFileFormat, FILE_FORMATS, real_ppath
from pbalign.utils.tempfileutil import TempFileManager
from pbalign.pbalignfiles import PBAlignFiles
from pbalign.filterservice import FilterService
from pbalign.bampostservice import BamPostService

class PBAlignRunner(PBToolRunner):

    """Tool runner."""

    def __init__(self, args=None, argumentList=(),
                 output_dataset_type=AlignmentSet):
        """Initialize a PBAlignRunner object.
           argumentList is a list of arguments, such as:
           ['--debug', '--maxHits', '10', 'in.fasta', 'ref.fasta', 'out.sam']
        """
        desc = "Utilities for aligning PacBio reads to reference sequences."
        if args is None: # FIXME unit testing hack
            args = get_contract_parser().arg_parser.parser.parse_args(argumentList)
        self.args = args
        # args.verbosity is computed by counting # of 'v's in '-vv...'.
        # However in parseOptions, arguments are parsed twice to import config
        # options and then overwrite them with argumentList (e.g. command-line)
        # options.
        #self.args.verbosity = 1 if (self.args.verbosity is None) else \
        #    (int(self.args.verbosity) / 2 + 1)
        super(PBAlignRunner, self).__init__(desc)
        self._output_dataset_type = output_dataset_type
        self._alnService = None
        self._filterService = None
        self.fileNames = PBAlignFiles()
        self._tempFileManager = TempFileManager()

    def _setupParsers(self, description):
        pass

    def _addStandardArguments(self):
        pass

    def getVersion(self):
        """Return version."""
        return get_version()

    def _createAlignService(self, name, args, fileNames, tempFileManager):
        """
        Create and return an AlignService by algorithm name.
        Input:
            name           : an algorithm name such as blasr
            fileNames      : an PBAlignFiles object
            args           : pbalign options
            tempFileManager: a temporary file manager
        Output:
            an object of AlignService subclass (such as BlasrService).
        """
        if name not in ALGORITHM_CANDIDATES:
            errMsg = "ERROR: unrecognized algorithm {algo}".format(algo=name)
            logging.error(errMsg)
            raise ValueError(errMsg)

        service = None
        if name == "blasr":
            service = BlasrService(args, fileNames, tempFileManager)
        elif name == "bowtie":
            service = BowtieService(args, fileNames, tempFileManager)
        elif name == "gmap":
            service = GMAPService(args, fileNames, tempFileManager)
        else:
            errMsg = "Service for {algo} is not implemented.".\
                     format(algo=name)
            logging.error(errMsg)
            raise ValueError(errMsg)

        service.checkAvailability()
        return service

    def _makeSane(self, args, fileNames):
        """
        Check whether the input arguments make sense or not.
        """
        errMsg = ""
        if args.useccs == "useccsdenovo":
            args.readType = "CCS"

        if fileNames.inputFileFormat == FILE_FORMATS.CCS:
            args.readType = "CCS"

        if args.forQuiver:
            logging.warning("Option --forQuiver has been deprecated in 3.0")

        outFormat = getFileFormat(fileNames.outputFileName)

        if outFormat == FILE_FORMATS.CMP:
            errMsg = "pbalign no longer supports CMP.H5 Output in 3.0."
            raise IOError(errMsg)

        if outFormat == FILE_FORMATS.BAM or outFormat == FILE_FORMATS.XML:
            if args.algorithm != "blasr":
                errMsg = "Must choose blasr in order to output a bam file."
                raise ValueError(errMsg)
            if args.filterAdapterOnly:
                errMsg = "-filterAdapter does not work when out format is BAM."
                raise ValueError(errMsg)

    def _parseArgs(self):
        """Overwrite ToolRunner.parseArgs(self).
        Parse PBAlignRunner arguments considering both args in argumentList and
        args in a config file (specified by --configFile).
        """
        pass

    def _output(self, inSam, refFile, outFile, readType=None):
        """Generate a SAM, BAM file.
        Input:
            inSam   : an input SAM/BAM file. (e.g. fileName.filteredSam)
            refFile : the reference file. (e.g. fileName.targetFileName)
            outFile : the output SAM/BAM file
                      (i.e. fileName.outputFileName)
            readType: standard or cDNA or CCS (can be None if not specified)
        Output:
            output, errCode, errMsg
        """
        output, errCode, errMsg = "", 0, ""

        outFormat = getFileFormat(outFile)

        if outFormat == FILE_FORMATS.BAM:
            pass # Nothing to be done
        if outFormat == FILE_FORMATS.SAM:
            logging.info("OutputService: Genearte the output SAM file.")
            logging.debug("OutputService: Move %s as %s", inSam, outFile)
            try:
                shutil.move(readlink(real_ppath(inSam)), real_ppath(outFile))
            except shutil.Error as e:
                output, errCode, errMsg = "", 1, "Exited with error: " + str(e)
                logging.error(errMsg)
                raise RuntimeError(errMsg)
        elif outFormat == FILE_FORMATS.CMP:
            errMsg = "pbalign no longer supports CMP.H5 Output in 3.0."
            logging.error(errMsg)
            raise IOError(errMsg)
        elif outFormat == FILE_FORMATS.XML:
            logging.info("OutputService: Generating the output XML file %s %s",
                         inSam, outFile)
            # Create {out}.xml, given {out}.bam
            outBam = str(outFile[0:-3]) + "bam"
            aln = None
            # FIXME This should really be more automatic
            if readType == "CCS":
                self._output_dataset_type = ConsensusAlignmentSet
            aln = self._output_dataset_type(real_ppath(outBam))
            for res in aln.externalResources:
                res.reference = refFile
            aln.write(outFile)

        return output, errCode, errMsg

    def _cleanUp(self, realDelete=False):
        """ Clean up temporary files and intermediate results. """
        logging.debug("Clean up temporary files and directories.")
        self._tempFileManager.CleanUp(realDelete)

    def run(self):
        """
        The main function, it is called by PBToolRunner.start().
        """
        startTime = time.time()
        logging.info("pbalign version: %s", get_version())
        #logging.debug("Original arguments: " + str(self._argumentList))

        # Create an AlignService by algorithm name.
        self._alnService = self._createAlignService(self.args.algorithm,
                                                    self.args,
                                                    self.fileNames,
                                                    self._tempFileManager)

        # Make sane.
        self._makeSane(self.args, self.fileNames)

        # Run align service.
        self._alnService.run()

        # Create a temporary filtered SAM/BAM file as output for FilterService.
        outFormat = getFileFormat(self.fileNames.outputFileName)
        suffix = ".bam" if outFormat in \
                [FILE_FORMATS.BAM, FILE_FORMATS.XML] else ".sam"
        self.fileNames.filteredSam = self._tempFileManager.\
            RegisterNewTmpFile(suffix=suffix)

        # Call filter service on SAM or BAM file.
        self._filterService = FilterService(self.fileNames.alignerSamOut,
                                            self.fileNames.targetFileName,
                                            self.fileNames.filteredSam,
                                            self.args.algorithm,
                                            #self._alnService.name,
                                            self._alnService.scoreSign,
                                            self.args,
                                            self.fileNames.adapterGffFileName)
        self._filterService.run()

        # Sort bam before output
        if outFormat in [FILE_FORMATS.BAM, FILE_FORMATS.XML]:
            # Sort/make index for BAM output.
            BamPostService(filenames=self.fileNames, nproc=self.args.nproc).run()

        # Output all hits in SAM, BAM.
        self._output(
            inSam=self.fileNames.filteredSam,
            refFile=self.fileNames.targetFileName,
            outFile=self.fileNames.outputFileName,
            readType=self.args.readType)

        # Delete temporay files anyway to make
        self._cleanUp(False if (hasattr(self.args, "keepTmpFiles") and
                                self.args.keepTmpFiles is True) else True)

        endTime = time.time()
        logging.info("Total time: {:.2f} s.".format(float(endTime - startTime)))
        return 0

def args_runner(args, output_dataset_type=AlignmentSet):
    """args runner"""
    # PBAlignRunner inherits PBToolRunner. So PBAlignRunner.start() parses args,
    # sets up logging and finally returns run().
    return PBAlignRunner(args, output_dataset_type=output_dataset_type).start()

def _resolved_tool_contract_runner(output_dataset_type,
                                   resolved_tool_contract):
    """
    Template function for running from a tool contract with an explicitly
    specified output dataset type.
    """
    args = resolved_tool_contract_to_args(resolved_tool_contract)
    return args_runner(args, output_dataset_type=output_dataset_type)

resolved_tool_contract_runner = functools.partial(
    _resolved_tool_contract_runner, AlignmentSet)
resolved_tool_contract_runner_ccs = functools.partial(
    _resolved_tool_contract_runner, ConsensusAlignmentSet)

def main(argv=sys.argv, get_parser_func=get_contract_parser,
         contract_runner_func=resolved_tool_contract_runner):
    """Main, supporting both args runner and tool contract runner."""
    return pbparser_runner(
        argv=argv[1:],
        parser=get_parser_func(),
        args_runner_func=args_runner,
        contract_runner_func=contract_runner_func,
        alog=logging.getLogger(__name__),
        setup_log_func=setup_log)

if __name__ == "__main__":
    sys.exit(main())
