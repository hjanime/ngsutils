#!/usr/bin/env python
## category RNA-seq
## desc Calculates counts/RPKM for genes/BED regions/repeats
'''
Counts the number of reads in genes or regions

This takes a gene/region model and a BAM file and calculates how many reads
show support of each gene/region.

Possible annotation models: gtf, exon, bed, repeat, repeatfam, or bin

[gtf]
    Calculate the number of reads that map within the coding regions of each
    gene. If [-norm] is given, an RPKM calculation is also performed,
    yielding the normalized RPKM value for each gene.

    Requires: GTF file
    Calculates: # reads, RPKM, coverage


[exon]
    Calculate the number of reads that map to each expressed region/exon
    for all genes. Also, for each gene, the reads mapping to consecutively
    constant regions are also found.  With these two numbers an alternative
    index is calculated (# reads in a region / # consec. const. reads).

    Regions can be exons, or parts of exons, depending on splicing (determined
    by isoform annotation).

    Requires: GTF file
    Calculates: # reads,
                RPKM,
                # const region reads for gene,
                # region reads,
                # region excluding reads (spliced out),
                Inclusion percentage
                Exclusion percentage
                alt-index

    Inclusion percentage = # including reads / # all reads
    Exclusion percentage = # excluding reads / # all reads

    Alt-index =     (# region reads) - (# region excluding reads)
                 ------------------------------------------------
                          (# non region reads for gene)

    Note: the alt-index is an experimental calculation that attempts to
    capture the amount that each region contributes to the overall read count
    for a gene. This is close to a percentage, except that we also take into
    account the number of reads that explicitly exclude a region. We divide by
    the number of non-region reads to account for changes that might be due to
    gene expression-level changes.



[bed]
    Calculates the number of reads in a region, where the region is defined
    in a BED6 formated file: chrom, start (0-based), end, name, score, strand.

    Requires: BED file
    Calculates: # reads, RPKM, coverage


[repeat]
    Calculates the number of reads that map to various repeat regions in the
    genome.  Repeat regions are defined by annotations from repeatmasker.org.
    Output is the number of reads that map to each repeat element.

    Requires: RepeatMasker file
    Calculates: # reads, RPKM

[repeatfam]
    Calculates the number of reads that map to various repeat regions in the
    genome.  Repeat regions are defined by annotations from repeatmasker.org.
    Output is the number of reads that map to each family/member of repeats.

    Requires: RepeatMasker file
    Calculates: # reads, RPKM

[bin]
    Calculates the number of reads in bins of N bases. Reads
    that span a bin-bin boundry will be counted for each bin. Valid
    normalization options: total, quantile, none. If quantile normalization
    is performed, only bins that include a read will be used.

    Requires: bin-size
    Calculates: # reads

Note: Output start positions are zero-based coordinates.

'''

import sys
import os

import count


def usage(msg=None):
    if msg:
        print 'Error: %s' % msg
    print __doc__
    print """\
Usage: bamutils count {opts} bamfile

Model options (you must select one):
    -gtf filename      Count reads for a genes based on a GTF model
    -exon filename     Count reads for each exon/expressed region (GTF model)
                       (alternative-splicing detection)
    -bed filename      Count reads in BED regions
    -repeat filename   Count reads in RepeatMasker.org defined repeat elements
    -repeatfam fname   Count reads in RepeatMasker.org defined repeat families
    -bin size          Count reads present in bins of {size} bases

Other options:
    -nostrand          ignore strand in counting reads
    -coverage          calculate average coverage for genes/regions
    -uniq              only count unique starting positions
                       (avoids possible PCR artifacts, not recommended)
    -rpkm              calculate RPKM values based on millions of mapped reads
                       and the length of the region in kb (number of mapped reads
                       determined by -norm value)
    -norm <value>      how to normalize counts
                       (adds counts-per-million (CPM) column)
    -multiple <value>  how to handle reads that map to multiple locations
    -whitelist file    file containing a white-list of read names
                       (only these read-names will be used in the calcs)
    -blacklist file    file containing a black-list of read names
                       (these read-names will not be used in the calcs)

Possible values for [-norm]:
    (If -norm is not given, can't be calculated)

    all         Use the number of all reads that mapped (anywhere)
    mapped      Use the number of reads that map in the model (genes/regions)
    median      Use the median value
                (genes/regions without reads excluded)
    quantile    Use the number of reads in the lower 75% of all genes/regions
                (genes/regions without reads excluded)

Possible values for [-multiple]:
    complete    Adds to the counts of all genes/regions (default)
                (Note: this can result in more 'counts' than reads)
    ignore      Don't add to the count of any genes/regions
    partial     Adds a fractional count to all genes/regions
                (1/number of matches, ex: IH:i:3 add 0.333 to each gene)

"""
    sys.exit(-1)

if __name__ == '__main__':
    stranded = True
    coverage = False
    uniq_only = False
    rpkm = False
    norm = None
    multiple = 'complete'
    whitelist = None
    blacklist = None
    model = None
    model_arg = None
    bamfile = None

    last = None

    for arg in sys.argv[1:]:
        if last in ['-%s' % x for x in count.models]:
            model_arg = arg
            last = None
        elif last == '-norm':
            if arg not in ['all', 'mapped', 'median', 'quantile', 'none']:
                usage('Invalid option for -norm: %s' % arg)
            if arg != 'none':
                norm = arg
            last = None
        elif last == '-multiple':
            if arg not in ['complete', 'ignore', 'partial']:
                usage('Invalid option for -multiple: %s' % arg)
            multiple = arg
            last = None
        elif last == '-whitelist':
            whitelist = []
            if not os.path.exists(arg):
                usage('Whitelist file does not exist: %s' % arg)
            with open(arg) as f:
                for line in f:
                    whitelist.append(line.strip())
        elif last == '-blacklist':
            blacklist = []
            if not os.path.exists(arg):
                usage('Blacklist file does not exist: %s' % arg)
            with open(arg) as f:
                for line in f:
                    blacklist.append(line.strip())
        elif arg in ['-%s' % x for x in count.models]:
            model = arg[1:]
            last = arg
        elif arg in ['-norm', '-multiple', '-whitelist', '-blacklist']:
            last = arg
        elif arg == '-nostrand':
            stranded = False
        elif arg == '-coverage':
            coverage = True
        elif arg == '-rpkm':
            rpkm = True
        elif arg == '-uniq':
            uniq_only = True
        elif arg == '-h':
            usage()
        elif not bamfile:
            if not os.path.exists(arg):
                usage('Missing or non-existant bamfile: %s' % arg)
            if not os.path.exists('%s.bai' % arg):
                usage('Missing bam index (bai) file: %s' % arg)

            bamfile = arg

    if not model or not model_arg:
        usage('Missing model! Must include one of: %s' % ', '.join(count.models))
    elif not bamfile:
        usage('Missing BAM file!')

    modelobj = count.models[model](model_arg)
    modelobj.count(bamfile, stranded, coverage, uniq_only, rpkm, norm, multiple, whitelist, blacklist)