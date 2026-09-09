//  KeychainStore.swift
//  Lo único que merece llavero: los tokens de OAuth.
//
//  El resto de ajustes viven en UserDefaults del grupo de apps, que no está
//  pensado para secretos. Aquí no se guarda nada de Sleeper: su API es pública
//  y no hay ninguna credencial que proteger.

import Foundation
import Security

enum KeychainStore {
    /// Servicio bajo el que se agrupan todas las entradas de la app.
    private static let service = "dev.calvi.sleeperscore.tokens"

    @discardableResult
    static func save(_ data: Data, for key: String) -> Bool {
        let consulta: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
        ]
        SecItemDelete(consulta as CFDictionary)

        var nueva = consulta
        nueva[kSecValueData as String] = data
        // Accesible tras el primer desbloqueo: si algún día el widget necesita
        // leerlo, puede hacerlo sin que el usuario tenga el móvil desbloqueado.
        nueva[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
        return SecItemAdd(nueva as CFDictionary, nil) == errSecSuccess
    }

    static func read(_ key: String) -> Data? {
        let consulta: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var resultado: CFTypeRef?
        guard SecItemCopyMatching(consulta as CFDictionary, &resultado) == errSecSuccess else {
            return nil
        }
        return resultado as? Data
    }

    @discardableResult
    static func delete(_ key: String) -> Bool {
        let consulta: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
        ]
        let estado = SecItemDelete(consulta as CFDictionary)
        return estado == errSecSuccess || estado == errSecItemNotFound
    }

    // MARK: - Objetos

    static func save<T: Encodable>(_ value: T, for key: String) {
        guard let data = try? SharedJSON.encoder.encode(value) else { return }
        save(data, for: key)
    }

    static func read<T: Decodable>(_ type: T.Type, for key: String) -> T? {
        guard let data = read(key) else { return nil }
        return try? SharedJSON.decoder.decode(type, from: data)
    }
}
