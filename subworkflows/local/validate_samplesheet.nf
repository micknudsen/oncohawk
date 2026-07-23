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
    def allowed = ['library_id', 'flowcell_id', 'lane', 'platform'] as Set
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
    values
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
        if( rowDiagnostics.isEmpty() && info.keySet().containsAll(['library_id', 'flowcell_id', 'lane']) && paths.every { path -> path } ) {
            records << [
                patient_id: fields[0], sample_id: fields[1], library_id: info.library_id,
                flowcell_id: info.flowcell_id, lane: info.lane, platform: info.platform,
                r1_path: paths[0], r2_path: paths[1], row: rowNumber
            ]
        }
    }

    def patientBySample = [:]
    def seenTuples = [] as Set
    records.each { record ->
        if( patientBySample.containsKey(record.sample_id) && patientBySample[record.sample_id] != record.patient_id ) {
            diagnostics << "row ${record.row}, sample_id: '${record.sample_id}' maps to more than one patient_id"
        }
        patientBySample[record.sample_id] = record.patient_id

        def tuple = [record.sample_id, record.library_id, record.flowcell_id, record.lane].join('|')
        if( !seenTuples.add(tuple) ) {
            diagnostics << "row ${record.row}: duplicate (sample_id, library_id, flowcell_id, lane) tuple"
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

    main:
    normalized_records = channel.fromPath(sample_sheet).map { path -> validateSamplesheet(path) }.flatMap { record -> record }

    emit:
    records = normalized_records
}
