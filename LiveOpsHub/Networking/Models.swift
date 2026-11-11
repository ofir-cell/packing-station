import Foundation

// Shapes mirror the Flask JSON responses. Every field the server may omit or
// send as null is optional, so a backend addition never breaks decoding.

struct SessionInfo: Decodable {
    let ok: Bool
    let signedIn: Bool
    let csrfToken: String?
    let minVersion: String?
    let user: String?
    let name: String?
    let role: String?
    let roles: [String]?
    let org: String?
    let companyName: String?

    enum CodingKeys: String, CodingKey {
        case ok, user, name, role, roles, org
        case signedIn = "signed_in", csrfToken = "csrf_token"
        case minVersion = "min_version", companyName = "company_name"
    }
}

struct OKResponse: Decodable {
    let ok: Bool
    let error: String?
    let message: String?
}

struct LoginResponse: Decodable {
    let ok: Bool
    let role: String?
    let error: String?
}

struct DeleteAccountResponse: Decodable {
    let ok: Bool
    let error: String?
    let message: String?
    let needOrgConfirm: Bool?
    let orgDeleted: Bool?
    enum CodingKeys: String, CodingKey {
        case ok, error, message
        case needOrgConfirm = "need_org_confirm", orgDeleted = "org_deleted"
    }
}

// MARK: - Orders

struct Shipment: Decodable, Hashable {
    let shipmentId: String
    let trackingCode: String?
    let buyerName: String?
    let buyerUsername: String?
    let status: String?
    let importLabel: String?
    let platform: String?
    let pickedBy: String?
    let packedBy: String?

    enum CodingKeys: String, CodingKey {
        case status, platform
        case shipmentId = "shipment_id", trackingCode = "tracking_code"
        case buyerName = "buyer_name", buyerUsername = "buyer_username"
        case importLabel = "import_label", pickedBy = "picked_by", packedBy = "packed_by"
    }

    var displayBuyer: String {
        if let n = buyerName, !n.isEmpty { return n }
        if let u = buyerUsername, !u.isEmpty { return "@" + u }
        return "Unknown buyer"
    }
}

struct LineItem: Decodable, Hashable, Identifiable {
    var id: String { (sku ?? "") + "|" + (productName ?? "") + "|" + String(quantity ?? 1) }
    let sku: String?
    let productName: String?
    let quantity: Int?
    enum CodingKeys: String, CodingKey { case sku, quantity; case productName = "product_name" }
}

struct ShipmentLookup: Decodable {
    let ok: Bool
    let error: String?
    let isGiveaway: Bool?
    let shipment: Shipment?
    let items: [LineItem]?
    let combinedFrom: [String]?
    enum CodingKeys: String, CodingKey {
        case ok, error, shipment, items
        case isGiveaway = "is_giveaway", combinedFrom = "combined_from"
    }
}

struct UploadResult: Decodable {
    let ok: Bool
    let error: String?
}

// MARK: - Picking

struct PickQueueRow: Decodable, Identifiable, Hashable {
    var id: String { shipmentId }
    let shipmentId: String
    let trackingCode: String?
    let buyerName: String?
    let buyerUsername: String?
    let importLabel: String?
    let platform: String?
    let itemCount: Int?
    let pickedCount: Int?
    let pickStartedBy: String?

    enum CodingKeys: String, CodingKey {
        case platform
        case shipmentId = "shipment_id", trackingCode = "tracking_code"
        case buyerName = "buyer_name", buyerUsername = "buyer_username"
        case importLabel = "import_label", itemCount = "item_count"
        case pickedCount = "picked_count", pickStartedBy = "pick_started_by"
    }

    var displayBuyer: String {
        if let n = buyerName, !n.isEmpty { return n }
        if let u = buyerUsername, !u.isEmpty { return "@" + u }
        return shipmentId
    }
}

struct PickItem: Decodable, Identifiable, Hashable {
    let id: Int
    let sku: String?
    let productName: String?
    let quantity: Int?
    var picked: Int
    let cancelled: Int?
    enum CodingKeys: String, CodingKey {
        case id, sku, quantity, picked, cancelled
        case productName = "product_name"
    }
    var isCancelled: Bool { (cancelled ?? 0) != 0 }
    var isPicked: Bool { picked != 0 }
}

struct PickDetail: Decodable {
    let ok: Bool
    let error: String?
    let shipment: Shipment?
    let items: [PickItem]?
    let cleanupBlocked: Bool?
    let cleanoutRequired: Bool?
    let alreadyPicked: Bool?
    let pickedBy: String?
    enum CodingKeys: String, CodingKey {
        case ok, error, shipment, items
        case cleanupBlocked = "cleanup_blocked", cleanoutRequired = "cleanout_required"
        case alreadyPicked = "already_picked", pickedBy = "picked_by"
    }
}

struct ToggleResponse: Decodable {
    let ok: Bool
    let picked: Int?
    let error: String?
}

// MARK: - Home

struct StatBlock: Decodable {
    let count: Int?
    let avgDur: Double?
    enum CodingKeys: String, CodingKey { case count; case avgDur = "avg_dur" }
}

struct MyStats: Decodable {
    let name: String?
    let role: String?
    let today: StatBlock?
    let thisMonth: StatBlock?
    let allTime: StatBlock?
    let rankThisMonth: Int?
    let totalWorkersThisMonth: Int?
    enum CodingKeys: String, CodingKey {
        case name, role, today
        case thisMonth = "this_month", allTime = "all_time"
        case rankThisMonth = "rank_this_month", totalWorkersThisMonth = "total_workers_this_month"
    }
}

struct ShowProgress: Decodable, Identifiable {
    var id: String { name }
    let name: String
    let total: Int
    let toPick: Int
    let toPack: Int
    let packed: Int?
    let shipped: Int?
    enum CodingKeys: String, CodingKey {
        case name, total, packed, shipped
        case toPick = "to_pick", toPack = "to_pack"
    }
}

struct Fulfillment: Decodable {
    let totalToPack: Int
    let totalToPick: Int
    let showsRemaining: Int
    let shows: [ShowProgress]
    enum CodingKeys: String, CodingKey {
        case shows
        case totalToPack = "total_to_pack", totalToPick = "total_to_pick"
        case showsRemaining = "shows_remaining"
    }
}
