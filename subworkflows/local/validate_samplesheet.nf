nextflow.enable.dsl=2

def diagnosticsForRow(int rowNumber, List<String> fields) {
    def diagnostics = []
    def names = ['patient_id', 'sample_id', 'filetype', 'info', 'filepath']

    if( fields.size() != names.size() ) {
        diagnostics << "row ${rowNumber}: expected exactly 5 CSV fields, found ${fields.size()}"
        return diagnostics
    }

    fields.eachWithIndex { value, index ->
        if( value.isEmpty() ) {
            diagnostics << "row ${rowNumber}, ${names[index]}: value is required"
        }
        else if( value.any { character -> Character.isWhitespace(character as char) } ) {
            diagnostics << "row ${rowNumber}, ${names[index]}: whitespace is not permitted"
        }
        if( value.contains('"') ) {
            diagnostics << "row ${rowNumber}, ${names[index]}: quoted CSV fields are not supported"
        }
    }

    if( fields[2] && fields[2] != 'fastq' ) {
        diagnostics << "row ${rowNumber}, filetype: must equal 'fastq'"
    }

    diagnostics
}

def parseInfo(int rowNumber, String value, List<String> diagnostics) {
    def allowed = ['library_id', 'flowcell_id', 'lane', 'platform', 'barcode'] as Set
    def required = ['library_id', 'flowcell_id', 'lane']
    def values = [:]

    if( value.isEmpty() || value.any { character -> Character.isWhitespace(character as char) } ) {
        return values
    }

    value.split(';', -1).each { entry ->
        def pair = entry.split(':', -1)
        if( pair.size() != 2 || pair[0].isEmpty() || pair[1].isEmpty() ) {
            diagnostics << "row ${rowNumber}, info: entries must be nonempty key:value pairs"
            return
        }
        if( !allowed.contains(pair[0]) ) {
            diagnostics << "row ${rowNumber}, info: unknown key '${pair[0]}'"
            return
        }
        if( values.containsKey(pair[0]) ) {
            diagnostics << "row ${rowNumber}, info: key '${pair[0]}' must occur exactly once"
            return
        }
        values[pair[0]] = pair[1]
    }

    required.each { key ->
        if( !values.containsKey(key) ) {
            diagnostics << "row ${rowNumber}, info: missing required key '${key}'"
        }
    }

    values.platform = values.platform ?: 'ILLUMINA'
    def samPlatforms = ['CAPILLARY', 'DNBSEQ', 'ELEMENT', 'HELICOS', 'ILLUMINA', 'IONTORRENT', 'LS454', 'ONT', 'PACBIO', 'SINGULAR', 'SOLID', 'ULTIMA'] as Set
    if( !samPlatforms.contains(values.platform) ) {
        diagnostics << "row ${rowNumber}, info: platform must be one of ${samPlatforms.join(', ')}"
    }
    if( values.containsKey('barcode') && !values.barcode.matches('[ACGTRYSWKMBDHVN]+(?:\\+[ACGTRYSWKMBDHVN]+)?') ) {
        diagnostics << "row ${rowNumber}, info: barcode must be one uppercase IUPAC DNA sequence or dual sequences joined by +"
    }
    values
}

def percentEncodeReadGroupComponent(Object value) {
    value.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8).collect { byteValue ->
        def codePoint = byteValue & 0xff
        if( (codePoint >= 0x41 && codePoint <= 0x5a) || (codePoint >= 0x61 && codePoint <= 0x7a) || (codePoint >= 0x30 && codePoint <= 0x39) || codePoint == 0x5f || codePoint == 0x2d ) {
            Character.toString(codePoint as char)
        }
        else {
            String.format('%%%02X', codePoint)
        }
    }.join()
}

def composeReadGroupValue(List<Object> components) {
    components.collect { component -> percentEncodeReadGroupComponent(component) }.join('.')
}

def parsePaths(int rowNumber, String value, Path sampleSheetDirectory, List<String> diagnostics) {
    def paths = value.split(';', -1)
    if( paths.size() != 2 || paths.any { path -> path.isEmpty() } ) {
        diagnostics << "row ${rowNumber}, filepath: must contain exactly two semicolon-separated paths"
        return [null, null]
    }
    if( !paths[0].matches('.*\\.(fastq|fq)\\.gz$') || !paths[0].replaceFirst('\\.(fastq|fq)\\.gz$', '').matches('.*(?:^|[_.-])R1(?:[_.-]|$).*') ) {
        diagnostics << "row ${rowNumber}, filepath: first path must name a .fastq.gz or .fq.gz file with an R1 mate token"
    }
    if( !paths[1].matches('.*\\.(fastq|fq)\\.gz$') || !paths[1].replaceFirst('\\.(fastq|fq)\\.gz$', '').matches('.*(?:^|[_.-])R2(?:[_.-]|$).*') ) {
        diagnostics << "row ${rowNumber}, filepath: second path must name a .fastq.gz or .fq.gz file with an R2 mate token"
    }

    paths.collect { rawPath ->
        def path = java.nio.file.Path.of(rawPath)
        path.isAbsolute() ? path.normalize().toString() : sampleSheetDirectory.resolve(path).normalize().toString()
    }
}

def validateFastqPaths(int rowNumber, List<String> paths, List<String> diagnostics) {
    def resolvedPaths = [null, null]

    paths.eachWithIndex { path, index ->
        def mate = index == 0 ? 'R1' : 'R2'
        def candidate = java.nio.file.Path.of(path)

        try {
            def resolved = candidate.toRealPath()
            if( !java.nio.file.Files.isRegularFile(resolved) ) {
                diagnostics << "row ${rowNumber}, filepath: ${mate} must resolve to a regular file"
            }
            else if( !java.nio.file.Files.isReadable(resolved) ) {
                diagnostics << "row ${rowNumber}, filepath: ${mate} must resolve to a readable file"
            }
            else {
                resolvedPaths[index] = resolved
            }
        }
        catch( java.nio.file.NoSuchFileException _ignored ) {
            diagnostics << "row ${rowNumber}, filepath: ${mate} path does not exist"
        }
        catch( java.nio.file.AccessDeniedException _ignored ) {
            diagnostics << "row ${rowNumber}, filepath: ${mate} path is not readable"
        }
        catch( java.io.IOException _ignored ) {
            diagnostics << "row ${rowNumber}, filepath: ${mate} path cannot be resolved"
        }
    }

    if( resolvedPaths.every { path -> path != null } ) {
        try {
            if( java.nio.file.Files.isSameFile(resolvedPaths[0], resolvedPaths[1]) ) {
                diagnostics << "row ${rowNumber}, filepath: R1 and R2 must resolve to distinct files"
            }
        }
        catch( java.io.IOException _ignored ) {
            diagnostics << "row ${rowNumber}, filepath: R1 and R2 paths cannot be compared"
        }
    }
}

def validateSamplesheet(sampleSheet) {
    def diagnostics = []
    def records = []
    def lines = java.nio.file.Files.readAllLines(sampleSheet)

    if( lines.isEmpty() ) {
        throw new IllegalArgumentException('sample sheet: file is empty')
    }

    lines[0] = lines[0].replaceFirst('^\\uFEFF', '')
    def expectedHeader = 'patient_id,sample_id,filetype,info,filepath'
    if( lines[0] != expectedHeader ) {
        diagnostics << "header: expected exactly '${expectedHeader}'"
    }

    def firstTrailingBlank = null
    (1..<lines.size()).each { index ->
        def line = lines[index]
        def rowNumber = index + 1
        if( line.isEmpty() ) {
            firstTrailingBlank = firstTrailingBlank ?: rowNumber
            return
        }
        if( firstTrailingBlank ) {
            diagnostics << "row ${rowNumber}: blank lines are permitted only at the end of the file"
            return
        }

        def fields = line.split(',', -1) as List<String>
        def rowDiagnostics = diagnosticsForRow(rowNumber, fields)
        diagnostics.addAll(rowDiagnostics)
        if( fields.size() != 5 ) {
            return
        }

        def info = parseInfo(rowNumber, fields[3], diagnostics)
        def paths = parsePaths(rowNumber, fields[4], sampleSheet.parent ?: java.nio.file.Path.of('.'), diagnostics)
        if( paths.every { path -> path } ) {
            validateFastqPaths(rowNumber, paths, diagnostics)
        }
        if( rowDiagnostics.isEmpty() && info.keySet().containsAll(['library_id', 'flowcell_id', 'lane']) && paths.every { path -> path } ) {
            def readGroupId = composeReadGroupValue([fields[1], info.library_id, info.flowcell_id, info.lane])
            def platformUnit = info.containsKey('barcode') ? composeReadGroupValue([info.flowcell_id, info.lane, info.barcode]) : readGroupId
            records << [
                patient_id: fields[0], sample_id: fields[1], library_id: info.library_id,
                flowcell_id: info.flowcell_id, lane: info.lane, platform: info.platform,
                barcode: info.barcode ?: null, read_group_id: readGroupId, platform_unit: platformUnit,
                r1_path: paths[0], r2_path: paths[1], row: rowNumber
            ]
        }
    }

    def patientBySample = [:]
    def seenTuples = [] as Set
    def seenReadGroupIds = [] as Set
    def seenPlatformUnits = [] as Set
    records.each { record ->
        if( patientBySample.containsKey(record.sample_id) && patientBySample[record.sample_id] != record.patient_id ) {
            diagnostics << "row ${record.row}, sample_id: '${record.sample_id}' maps to more than one patient_id"
        }
        patientBySample[record.sample_id] = record.patient_id

        def tuple = [record.sample_id, record.library_id, record.flowcell_id, record.lane].join('|')
        if( !seenTuples.add(tuple) ) {
            diagnostics << "row ${record.row}: duplicate (sample_id, library_id, flowcell_id, lane) tuple"
        }
        if( !seenReadGroupIds.add(record.read_group_id) ) {
            diagnostics << "row ${record.row}: duplicate generated read_group_id '${record.read_group_id}'"
        }
        if( !seenPlatformUnits.add(record.platform_unit) ) {
            diagnostics << "row ${record.row}: duplicate generated platform_unit '${record.platform_unit}'"
        }
    }

    if( diagnostics ) {
        throw new IllegalArgumentException("Sample-sheet validation failed:\n- ${diagnostics.join('\n- ')}")
    }

    records.collect { record -> record.findAll { key, _value -> key != 'row' } }
}

workflow VALIDATE_SAMPLESHEET {
    take:
    sample_sheet

    emit:
    channel.fromPath(sample_sheet).map { path -> validateSamplesheet(path) }.flatMap { record -> record }
}
