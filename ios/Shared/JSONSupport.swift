//  JSONSupport.swift
//  Pequeñas ayudas para leer JSON que no siempre viene como uno espera.

import Foundation

struct AnyCodingKey: CodingKey {
    var stringValue: String
    var intValue: Int?

    init?(stringValue: String) {
        self.stringValue = stringValue
        self.intValue = nil
    }

    init?(intValue: Int) {
        self.stringValue = String(intValue)
        self.intValue = intValue
    }
}

/// Diccionario de textos que no se rompe si algún valor no es un texto:
/// los números se convierten y lo demás se descarta.
struct LenientStringDictionary: Decodable {
    let values: [String: String]

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: AnyCodingKey.self)
        var result: [String: String] = [:]
        for key in container.allKeys {
            if let text = try? container.decode(String.self, forKey: key) {
                result[key.stringValue] = text
            } else if let number = try? container.decode(Int.self, forKey: key) {
                result[key.stringValue] = String(number)
            }
        }
        values = result
    }
}

enum SharedJSON {
    static var encoder: JSONEncoder {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        return encoder
    }

    static var decoder: JSONDecoder {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return decoder
    }
}

/// Hash estable entre arranques (el `hashValue` de Swift no lo es), para
/// nombrar los archivos de la caché de avatares.
func stableHash(_ text: String) -> String {
    var hash: UInt64 = 0xcbf2_9ce4_8422_2325
    for byte in Array(text.utf8) {
        hash ^= UInt64(byte)
        hash = hash &* 0x0000_0100_0000_01B3
    }
    return String(hash, radix: 16)
}
