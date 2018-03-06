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


# Author: Yuan Li

"""This scripts defines functions for handling input and output files."""

from __future__ import absolute_import
import os
import os.path as op
import logging
from xml.etree import ElementTree as ET
from pbcore.util.Process import backticks
from pbcore.io import DataSet, ReferenceSet


def enum(**enums):
    """Simulate enum."""
    return type('Enum', (), enums)

FILE_FORMATS = enum(FASTA="FASTA", PLS="PLS_H5", PLX="PLX_H5",
                    BAS="BAS_H5", BAX="BAX_H5", FOFN="FOFN",
                    SAM="SAM", CMP="CMP_H5", RGN="RGN_H5",
                    SA="SA", XML="XML", UNKNOWN="UNKNOWN",
                    CCS="CCS_H5", BAM="BAM")

VALID_INPUT_FORMATS = (FILE_FORMATS.FASTA, FILE_FORMATS.PLS,
                       FILE_FORMATS.PLX,   FILE_FORMATS.BAS,
                       FILE_FORMATS.BAX,   FILE_FORMATS.FOFN,
                       FILE_FORMATS.CCS,   FILE_FORMATS.BAM,
                       FILE_FORMATS.XML)

VALID_REGIONTABLE_FORMATS = (FILE_FORMATS.RGN, FILE_FORMATS.FOFN)

VALID_OUTPUT_FORMATS = (FILE_FORMATS.CMP, FILE_FORMATS.SAM,
                        FILE_FORMATS.BAM, FILE_FORMATS.XML)


def real_ppath(fn):
    """Return real 'python-style' path of a file.
    Consider files with white spaces in their paths, such as
    'res\ with\ space/out.sam' or 'res with space/out.sam',
    'res\ with\ space/out.sam' is unix-style file path.
    'res with space/out.sam' is python style file path.

    We need to convert all '\_' in path to ' ' so that python
    can handle files with space correctly, which means that
    'res\ with\ space/out.sam' will be converted to
    'res with space/out.sam'.
    """
    return op.abspath(op.expanduser(fn)).replace(r'\ ', ' ')


def real_upath(fn):
    """Return real 'unix-style' path of a file.
    Consider files with white spaces in their paths, such as
    'res\ with\ space/out.sam' or 'res with space/out.sam',
    'res\ with\ space/out.sam' is unix-style file path.
    'res with space/out.sam' is python style file path.

    We need to convert all ' ' to '\ ' so that unix can handle
    files with space correctly, which means that
    'res with space/out.sam' will be converted to
    'res\ with\ space/out.sam'.
    """
    return real_ppath(fn).replace(' ', r'\ ')


def isExist(ff):
    """Return whether a file or a dir ff exists or not.
    Call listdir first to eliminate NFS errors.
    """
    if not ff:
        return False
    try:
        # Might sync cache for some users.
        os.stat(ff)
    except Exception:
        pass
    try:
        # Might sync cache for some users.
        d = os.path.normpath(os.path.dirname(ff))
        os.listdir(d)
    except Exception:
        pass
    return os.path.exists(ff) # Broken symlink is also False.


def isValidInputFormat(ff):
    """Return True if ff is a valid input file format."""
    return ff in VALID_INPUT_FORMATS


def isValidOutputFormat(ff):
    """Return True if ff is a valid output file format."""
    return ff in VALID_OUTPUT_FORMATS


def isValidRegionTableFormat(ff):
    """Return true if ff is a valid region table file format."""
    return ff in VALID_REGIONTABLE_FORMATS


def getFileFormat(filename):
    """Verify and return a file's format.

    If a file format is supported, return the format. Otherwise,
    return FILE_FORMATS.UNKOWN.

    """
    base, ext = op.splitext(filename)
    ext = ext.lower()
    if ext in [".fa", ".fasta", ".fsta", ".fna"]:
        return FILE_FORMATS.FASTA
    elif ext in [".sam"]:
        return FILE_FORMATS.SAM
    elif ext in [".bam"]:
        return FILE_FORMATS.BAM
    elif ext in [".sa"]:
        return FILE_FORMATS.SA
    elif ext in [".fofn"]:
        return FILE_FORMATS.FOFN
    elif ext in [".xml"]:
        return FILE_FORMATS.XML
    elif ext in [".h5"]:
        ext = op.splitext(base)[1].lower()
        if ext in [".pls"]:
            return FILE_FORMATS.PLS
        elif ext in [".plx"]:
            return FILE_FORMATS.PLX
        elif ext in [".bas"]:
            return FILE_FORMATS.BAX
        elif ext in [".bax"]:
            return FILE_FORMATS.BAX
        elif ext in [".cmp"]:
            return FILE_FORMATS.CMP
        elif ext in [".rgn"]:
            return FILE_FORMATS.RGN
        elif ext in [".ccs"]:
            return FILE_FORMATS.CCS
    return FILE_FORMATS.UNKNOWN


def getFilesFromFOFN(fofnname):
    """
    Given a fofn file, return a list of absolute path of
    all files in fofn.
    """
    lines = []
    with open(real_ppath(fofnname), 'r') as f:
        lines = f.readlines()

    lines.sort()
    return [real_upath(l.strip()) for l in lines]


def getFileFormatsFromFOFN(fofnname):
    """
    Given a fofn file, return a list of file formats of
    all files in this fofn.
    """
    fs = getFilesFromFOFN(fofnname)
    return [getFileFormat(f) for f in fs]

def checkInputFile(filename, validFormats=VALID_INPUT_FORMATS):
    """
    Check whether an input file has the valid file format and exists.
    If an input file is a fofn, check whether all files names in the
    fofn exist.
    Return a list of absolute paths of all input files.
    """
    filename = real_ppath(filename)
    if not getFileFormat(filename) in validFormats:
        errMsg = "The input file format can only be {fm}.".format(
            fm=",".join(validFormats))
        logging.error(errMsg)
        raise IOError(errMsg)

    if not isExist(filename):
        errMsg = "Input file {fn} does not exist.".format(fn=filename)
        logging.error(errMsg)
        raise IOError(errMsg)

    if getFileFormat(filename) == FILE_FORMATS.FOFN:
        fileList = getFilesFromFOFN(filename)
        if len(fileList) == 0:
            errMsg = "FOFN file {fn} is empty.".format(fn=filename)
            logging.error(errMsg)
            raise ValueError(errMsg)
        fileListRet = []
        for f in fileList:
            if not isExist(f):
                errMsg = "A file in the fofn {fn} does not exist.".format(fn=f)
                logging.error(errMsg)
                raise IOError(errMsg)
            else:
                fileListRet.append(f)

    return real_upath(filename)


def getRealFileFormat(filename):
    """Return file format if filename is not a FOFN, otherwise return format
    of the first file within FOFN."""
    if getFileFormat(filename) == FILE_FORMATS.FOFN:
        fileList = getFilesFromFOFN(filename)
        assert len(fileList) != 0
        return getFileFormat(fileList[0])
    else:
        return getFileFormat(filename)


def checkRegionTableFile(filename):
    """
    Check whether the specified region table has the right format and exists.
    Return absolute path of the region table file.
    """
    if filename is None:
        return None
    return checkInputFile(filename, validFormats=VALID_REGIONTABLE_FORMATS)


def checkOutputFile(filename):
    """
    Check whether an output file is writable or not.
    Return absolute path of the output file.
    """
    filename = real_ppath(filename)
    if not isValidOutputFormat(getFileFormat(filename)):
        errMsg = "The output file format can only be CMP.H5, SAM, BAM or XML."
        logging.error(errMsg)
        raise ValueError(errMsg)
    try:
        with open(filename, "a"):
            pass
    except IOError as e:
        errMsg = "Could not access output file {fn}.".format(fn=filename)
        logging.error(errMsg)
        raise IOError(errMsg + str(e))
    return real_upath(filename)


class ReferenceInfo:

    """Parse reference.info.xml in reference path."""

    def __init__(self, fileName):
        fileName = real_ppath(fileName)
        if getFileFormat(fileName) != FILE_FORMATS.XML:
            errMsg = "The reference info file is not in XML format."
            raise ValueError(errMsg)
        self.dirname = op.dirname(fileName)
        self.refFastaFile = None
        self.refSawriterFile = None
        self.desc = None
        self.adapterGffFile = None
        self.fileName = real_upath(fileName)
        self._parse()

    def __repr__(self):
        """ Represent a reference info object."""
        desc = "Reference Info Object:"
        desc += "File Name: {f}".format(f=self.fileName)
        desc += "Reference FASTA File: {f}".format(f=self.refFastaFile)
        desc += "Reference Suffix Array File: {f}".format(
            f=self.refSawriterFile)
        desc += "Description: {d}".format(d=self.desc)
        if self.adapterGffFile is not None:
            desc += "Adapter GFF file: {f}".format(f=self.adapterGffFile)
        return desc

    def _parse(self):
        """Parse reference.info.xml in reference folder."""
        fileName = real_ppath(self.fileName)
        if isExist(fileName):
            try:
                tree = ET.parse(fileName)
                root = tree.getroot()
                ref = root.find("reference")
                refFile = ref.find("file")
                refFormat = refFile.get("format")
                if refFormat.lower().find("text/fasta") != -1:
                    self.refFastaFile = real_upath(op.join(
                        self.dirname, op.relpath(refFile.text)))
                else:
                    errMsg = "Could not find the reference fasta " + \
                             "file in reference.info.xml."
                    raise IOError(errMsg)

                for node in ref.getchildren():
                    if node.tag == "description":
                        self.desc = node.text
                    if node.tag == "index_file" and \
                       node.get("type").lower() == "sawriter":
                        self.refSawriterFile = real_upath(op.join(
                            self.dirname, op.relpath(node.text)))

                # Get the adapter annotation GFF file
                annotations = root.findall("annotations/annotation")
                for annotation in annotations:
                    if annotation.get("type") == "adapter":
                        self.adapterGffFile = real_upath(op.join(
                            self.dirname, annotation.find("file").text))
                        break
            except IOError as e:
                raise IOError(str(e))
            except ET.ParseError as e:
                errMsg = "Failed to parse {f}".format(f=fileName)
                raise ET.ParseError(errMsg)
        else:
            errMsg = "{fn} is not a valid reference info file."\
                .format(fn=fileName)
            raise IOError(errMsg)


def checkReferencePath(inRefpath):
    """Validate input reference path.
    Check whether the input reference path exists or not.
    Input : can be a FASTA file, a XML file or a reference repository.
    Output: [refpath, FASTA_file, None, False, gff], if input is a FASTA file,
            and it is not located within a reference repository.
            [refpath, FASTA_file, SA_file, True, gff], if input is a FASTA
            file, and it is located within a reference repository.
            [refpath, FASTA_file, None, False, None], if input is a XML
            [refpath, FASTA_file, SA_file, True, gff], if input is a reference
            repository produced by PacBio referenceUploader.
    """
    fastaFile, sawriterFile, refinfoxml = None, None, None
    isWithinRepository, adapterGffFile = None, None
    refpath = real_ppath(inRefpath)
    if not isExist(refpath):  # The inRefpath does not exist.
        errMsg = "The input path {refpath} does not exist.".format(
                 refpath=refpath)
        logging.error(errMsg)
        raise IOError(errMsg)

    if getFileFormat(refpath) == FILE_FORMATS.FASTA:
        fastaFile = refpath
        # Assume the input FASTA file is also located within a
        # reference repository
        refinfoxml = op.join(op.split(op.dirname(refpath))[0],
                             "reference.info.xml")
    elif getFileFormat(refpath) == FILE_FORMATS.XML:
        fastaFiles = ReferenceSet(refpath).toFofn()
        if len(fastaFiles) != 1:
            errMsg = refpath + " must contain exactly one reference"
            logging.error(errMsg)
            raise Exception(errMsg)
        fastaFile = fastaFiles[0][5:] if fastaFiles[0].startswith('file:') \
                else fastaFiles[0]
        refinfoxml = op.join(op.split(op.dirname(refpath))[0],
                             "reference.info.xml")
    else:
        refinfoxml = op.join(refpath, "reference.info.xml")

    # Check if refpath is a reference repository produced by
    # referenceUploader or is a FASTA file located within a reference
    # repository.
    try:
        refinfoobj = ReferenceInfo(refinfoxml)
        isWithinRepository = True
        fastaFile = refinfoobj.refFastaFile
        sawriterFile = refinfoobj.refSawriterFile
        adapterGffFile = refinfoobj.adapterGffFile
    except Exception as e:
        isWithinRepository = False
        if fastaFile is None:
            errMsg = "Could not find reference fasta file, please " + \
                     "check %s.\n" % refpath + str(e)
            logging.error(errMsg)
            raise IOError(errMsg)

    if getFileFormat(fastaFile) != FILE_FORMATS.FASTA:
        errMsg = "The reference file specified is not in FASTA format. " + \
                 "Please check %s." % refpath
        logging.error(errMsg)
        raise IOError(errMsg)

    if (sawriterFile is not None) and \
       ((getFileFormat(sawriterFile) != FILE_FORMATS.SA) or
            (not isExist(sawriterFile))):
        errMsg = "Could not found the sawriter file {f}".format(f=sawriterFile)
        logging.warn(errMsg)
        sawriterFile = None

    if (sawriterFile is not None):
        sawriterFile = real_upath(sawriterFile)

    return real_upath(refpath), real_upath(fastaFile), sawriterFile, \
           isWithinRepository, adapterGffFile

# if __name__ == "__main__":
#    refPath = "/opt/smrtanalysis" + \
#              "/common/references/lambda/"
#    refpath, faFile, saFile, isWithinRepository = checkReferencePath(refPath)
#    assert(faFile == refPath + "sequence/" + "lambda.fasta")
#    assert(saFile == refPath + "sequence/" + "lambda.fasta.sa")
#    assert(checkInputFile(faFile) == faFile)
#    assert(checkOutputFile("abc.sam") != "")
