//
// Generated file, do not edit! Created by opp_msgtool 6.0 from MeshPacket.msg.
//

// Disable warnings about unused variables, empty switch stmts, etc:
#ifdef _MSC_VER
#  pragma warning(disable:4101)
#  pragma warning(disable:4065)
#endif

#if defined(__clang__)
#  pragma clang diagnostic ignored "-Wshadow"
#  pragma clang diagnostic ignored "-Wconversion"
#  pragma clang diagnostic ignored "-Wunused-parameter"
#  pragma clang diagnostic ignored "-Wc++98-compat"
#  pragma clang diagnostic ignored "-Wunreachable-code-break"
#  pragma clang diagnostic ignored "-Wold-style-cast"
#elif defined(__GNUC__)
#  pragma GCC diagnostic ignored "-Wshadow"
#  pragma GCC diagnostic ignored "-Wconversion"
#  pragma GCC diagnostic ignored "-Wunused-parameter"
#  pragma GCC diagnostic ignored "-Wold-style-cast"
#  pragma GCC diagnostic ignored "-Wsuggest-attribute=noreturn"
#  pragma GCC diagnostic ignored "-Wfloat-conversion"
#endif

#include <iostream>
#include <sstream>
#include <memory>
#include <type_traits>
#include "MeshPacket_m.h"

namespace omnetpp {

// Template pack/unpack rules. They are declared *after* a1l type-specific pack functions for multiple reasons.
// They are in the omnetpp namespace, to allow them to be found by argument-dependent lookup via the cCommBuffer argument

// Packing/unpacking an std::vector
template<typename T, typename A>
void doParsimPacking(omnetpp::cCommBuffer *buffer, const std::vector<T,A>& v)
{
    int n = v.size();
    doParsimPacking(buffer, n);
    for (int i = 0; i < n; i++)
        doParsimPacking(buffer, v[i]);
}

template<typename T, typename A>
void doParsimUnpacking(omnetpp::cCommBuffer *buffer, std::vector<T,A>& v)
{
    int n;
    doParsimUnpacking(buffer, n);
    v.resize(n);
    for (int i = 0; i < n; i++)
        doParsimUnpacking(buffer, v[i]);
}

// Packing/unpacking an std::list
template<typename T, typename A>
void doParsimPacking(omnetpp::cCommBuffer *buffer, const std::list<T,A>& l)
{
    doParsimPacking(buffer, (int)l.size());
    for (typename std::list<T,A>::const_iterator it = l.begin(); it != l.end(); ++it)
        doParsimPacking(buffer, (T&)*it);
}

template<typename T, typename A>
void doParsimUnpacking(omnetpp::cCommBuffer *buffer, std::list<T,A>& l)
{
    int n;
    doParsimUnpacking(buffer, n);
    for (int i = 0; i < n; i++) {
        l.push_back(T());
        doParsimUnpacking(buffer, l.back());
    }
}

// Packing/unpacking an std::set
template<typename T, typename Tr, typename A>
void doParsimPacking(omnetpp::cCommBuffer *buffer, const std::set<T,Tr,A>& s)
{
    doParsimPacking(buffer, (int)s.size());
    for (typename std::set<T,Tr,A>::const_iterator it = s.begin(); it != s.end(); ++it)
        doParsimPacking(buffer, *it);
}

template<typename T, typename Tr, typename A>
void doParsimUnpacking(omnetpp::cCommBuffer *buffer, std::set<T,Tr,A>& s)
{
    int n;
    doParsimUnpacking(buffer, n);
    for (int i = 0; i < n; i++) {
        T x;
        doParsimUnpacking(buffer, x);
        s.insert(x);
    }
}

// Packing/unpacking an std::map
template<typename K, typename V, typename Tr, typename A>
void doParsimPacking(omnetpp::cCommBuffer *buffer, const std::map<K,V,Tr,A>& m)
{
    doParsimPacking(buffer, (int)m.size());
    for (typename std::map<K,V,Tr,A>::const_iterator it = m.begin(); it != m.end(); ++it) {
        doParsimPacking(buffer, it->first);
        doParsimPacking(buffer, it->second);
    }
}

template<typename K, typename V, typename Tr, typename A>
void doParsimUnpacking(omnetpp::cCommBuffer *buffer, std::map<K,V,Tr,A>& m)
{
    int n;
    doParsimUnpacking(buffer, n);
    for (int i = 0; i < n; i++) {
        K k; V v;
        doParsimUnpacking(buffer, k);
        doParsimUnpacking(buffer, v);
        m[k] = v;
    }
}

// Default pack/unpack function for arrays
template<typename T>
void doParsimArrayPacking(omnetpp::cCommBuffer *b, const T *t, int n)
{
    for (int i = 0; i < n; i++)
        doParsimPacking(b, t[i]);
}

template<typename T>
void doParsimArrayUnpacking(omnetpp::cCommBuffer *b, T *t, int n)
{
    for (int i = 0; i < n; i++)
        doParsimUnpacking(b, t[i]);
}

// Default rule to prevent compiler from choosing base class' doParsimPacking() function
template<typename T>
void doParsimPacking(omnetpp::cCommBuffer *, const T& t)
{
    throw omnetpp::cRuntimeError("Parsim error: No doParsimPacking() function for type %s", omnetpp::opp_typename(typeid(t)));
}

template<typename T>
void doParsimUnpacking(omnetpp::cCommBuffer *, T& t)
{
    throw omnetpp::cRuntimeError("Parsim error: No doParsimUnpacking() function for type %s", omnetpp::opp_typename(typeid(t)));
}

}  // namespace omnetpp

namespace lora_mesh {

Register_Class(MeshPacket)

MeshPacket::MeshPacket() : ::inet::FieldsChunk()
{
}

MeshPacket::MeshPacket(const MeshPacket& other) : ::inet::FieldsChunk(other)
{
    copy(other);
}

MeshPacket::~MeshPacket()
{
}

MeshPacket& MeshPacket::operator=(const MeshPacket& other)
{
    if (this == &other) return *this;
    ::inet::FieldsChunk::operator=(other);
    copy(other);
    return *this;
}

void MeshPacket::copy(const MeshPacket& other)
{
    this->sourceAddress = other.sourceAddress;
    this->destinationGateway = other.destinationGateway;
    this->hopCount = other.hopCount;
    this->sequenceNumber = other.sequenceNumber;
}

void MeshPacket::parsimPack(omnetpp::cCommBuffer *b) const
{
    ::inet::FieldsChunk::parsimPack(b);
    doParsimPacking(b,this->sourceAddress);
    doParsimPacking(b,this->destinationGateway);
    doParsimPacking(b,this->hopCount);
    doParsimPacking(b,this->sequenceNumber);
}

void MeshPacket::parsimUnpack(omnetpp::cCommBuffer *b)
{
    ::inet::FieldsChunk::parsimUnpack(b);
    doParsimUnpacking(b,this->sourceAddress);
    doParsimUnpacking(b,this->destinationGateway);
    doParsimUnpacking(b,this->hopCount);
    doParsimUnpacking(b,this->sequenceNumber);
}

const ::inet::L3Address& MeshPacket::getSourceAddress() const
{
    return this->sourceAddress;
}

void MeshPacket::setSourceAddress(const ::inet::L3Address& sourceAddress)
{
    handleChange();
    this->sourceAddress = sourceAddress;
}

const ::inet::L3Address& MeshPacket::getDestinationGateway() const
{
    return this->destinationGateway;
}

void MeshPacket::setDestinationGateway(const ::inet::L3Address& destinationGateway)
{
    handleChange();
    this->destinationGateway = destinationGateway;
}

int MeshPacket::getHopCount() const
{
    return this->hopCount;
}

void MeshPacket::setHopCount(int hopCount)
{
    handleChange();
    this->hopCount = hopCount;
}

int MeshPacket::getSequenceNumber() const
{
    return this->sequenceNumber;
}

void MeshPacket::setSequenceNumber(int sequenceNumber)
{
    handleChange();
    this->sequenceNumber = sequenceNumber;
}

class MeshPacketDescriptor : public omnetpp::cClassDescriptor
{
  private:
    mutable const char **propertyNames;
    enum FieldConstants {
        FIELD_sourceAddress,
        FIELD_destinationGateway,
        FIELD_hopCount,
        FIELD_sequenceNumber,
    };
  public:
    MeshPacketDescriptor();
    virtual ~MeshPacketDescriptor();

    virtual bool doesSupport(omnetpp::cObject *obj) const override;
    virtual const char **getPropertyNames() const override;
    virtual const char *getProperty(const char *propertyName) const override;
    virtual int getFieldCount() const override;
    virtual const char *getFieldName(int field) const override;
    virtual int findField(const char *fieldName) const override;
    virtual unsigned int getFieldTypeFlags(int field) const override;
    virtual const char *getFieldTypeString(int field) const override;
    virtual const char **getFieldPropertyNames(int field) const override;
    virtual const char *getFieldProperty(int field, const char *propertyName) const override;
    virtual int getFieldArraySize(omnetpp::any_ptr object, int field) const override;
    virtual void setFieldArraySize(omnetpp::any_ptr object, int field, int size) const override;

    virtual const char *getFieldDynamicTypeString(omnetpp::any_ptr object, int field, int i) const override;
    virtual std::string getFieldValueAsString(omnetpp::any_ptr object, int field, int i) const override;
    virtual void setFieldValueAsString(omnetpp::any_ptr object, int field, int i, const char *value) const override;
    virtual omnetpp::cValue getFieldValue(omnetpp::any_ptr object, int field, int i) const override;
    virtual void setFieldValue(omnetpp::any_ptr object, int field, int i, const omnetpp::cValue& value) const override;

    virtual const char *getFieldStructName(int field) const override;
    virtual omnetpp::any_ptr getFieldStructValuePointer(omnetpp::any_ptr object, int field, int i) const override;
    virtual void setFieldStructValuePointer(omnetpp::any_ptr object, int field, int i, omnetpp::any_ptr ptr) const override;
};

Register_ClassDescriptor(MeshPacketDescriptor)

MeshPacketDescriptor::MeshPacketDescriptor() : omnetpp::cClassDescriptor(omnetpp::opp_typename(typeid(lora_mesh::MeshPacket)), "inet::FieldsChunk")
{
    propertyNames = nullptr;
}

MeshPacketDescriptor::~MeshPacketDescriptor()
{
    delete[] propertyNames;
}

bool MeshPacketDescriptor::doesSupport(omnetpp::cObject *obj) const
{
    return dynamic_cast<MeshPacket *>(obj)!=nullptr;
}

const char **MeshPacketDescriptor::getPropertyNames() const
{
    if (!propertyNames) {
        static const char *names[] = {  nullptr };
        omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
        const char **baseNames = base ? base->getPropertyNames() : nullptr;
        propertyNames = mergeLists(baseNames, names);
    }
    return propertyNames;
}

const char *MeshPacketDescriptor::getProperty(const char *propertyName) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    return base ? base->getProperty(propertyName) : nullptr;
}

int MeshPacketDescriptor::getFieldCount() const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    return base ? 4+base->getFieldCount() : 4;
}

unsigned int MeshPacketDescriptor::getFieldTypeFlags(int field) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldTypeFlags(field);
        field -= base->getFieldCount();
    }
    static unsigned int fieldTypeFlags[] = {
        0,    // FIELD_sourceAddress
        0,    // FIELD_destinationGateway
        FD_ISEDITABLE,    // FIELD_hopCount
        FD_ISEDITABLE,    // FIELD_sequenceNumber
    };
    return (field >= 0 && field < 4) ? fieldTypeFlags[field] : 0;
}

const char *MeshPacketDescriptor::getFieldName(int field) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldName(field);
        field -= base->getFieldCount();
    }
    static const char *fieldNames[] = {
        "sourceAddress",
        "destinationGateway",
        "hopCount",
        "sequenceNumber",
    };
    return (field >= 0 && field < 4) ? fieldNames[field] : nullptr;
}

int MeshPacketDescriptor::findField(const char *fieldName) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    int baseIndex = base ? base->getFieldCount() : 0;
    if (strcmp(fieldName, "sourceAddress") == 0) return baseIndex + 0;
    if (strcmp(fieldName, "destinationGateway") == 0) return baseIndex + 1;
    if (strcmp(fieldName, "hopCount") == 0) return baseIndex + 2;
    if (strcmp(fieldName, "sequenceNumber") == 0) return baseIndex + 3;
    return base ? base->findField(fieldName) : -1;
}

const char *MeshPacketDescriptor::getFieldTypeString(int field) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldTypeString(field);
        field -= base->getFieldCount();
    }
    static const char *fieldTypeStrings[] = {
        "inet::L3Address",    // FIELD_sourceAddress
        "inet::L3Address",    // FIELD_destinationGateway
        "int",    // FIELD_hopCount
        "int",    // FIELD_sequenceNumber
    };
    return (field >= 0 && field < 4) ? fieldTypeStrings[field] : nullptr;
}

const char **MeshPacketDescriptor::getFieldPropertyNames(int field) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldPropertyNames(field);
        field -= base->getFieldCount();
    }
    switch (field) {
        default: return nullptr;
    }
}

const char *MeshPacketDescriptor::getFieldProperty(int field, const char *propertyName) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldProperty(field, propertyName);
        field -= base->getFieldCount();
    }
    switch (field) {
        default: return nullptr;
    }
}

int MeshPacketDescriptor::getFieldArraySize(omnetpp::any_ptr object, int field) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldArraySize(object, field);
        field -= base->getFieldCount();
    }
    MeshPacket *pp = omnetpp::fromAnyPtr<MeshPacket>(object); (void)pp;
    switch (field) {
        default: return 0;
    }
}

void MeshPacketDescriptor::setFieldArraySize(omnetpp::any_ptr object, int field, int size) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount()){
            base->setFieldArraySize(object, field, size);
            return;
        }
        field -= base->getFieldCount();
    }
    MeshPacket *pp = omnetpp::fromAnyPtr<MeshPacket>(object); (void)pp;
    switch (field) {
        default: throw omnetpp::cRuntimeError("Cannot set array size of field %d of class 'MeshPacket'", field);
    }
}

const char *MeshPacketDescriptor::getFieldDynamicTypeString(omnetpp::any_ptr object, int field, int i) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldDynamicTypeString(object,field,i);
        field -= base->getFieldCount();
    }
    MeshPacket *pp = omnetpp::fromAnyPtr<MeshPacket>(object); (void)pp;
    switch (field) {
        default: return nullptr;
    }
}

std::string MeshPacketDescriptor::getFieldValueAsString(omnetpp::any_ptr object, int field, int i) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldValueAsString(object,field,i);
        field -= base->getFieldCount();
    }
    MeshPacket *pp = omnetpp::fromAnyPtr<MeshPacket>(object); (void)pp;
    switch (field) {
        case FIELD_sourceAddress: return pp->getSourceAddress().str();
        case FIELD_destinationGateway: return pp->getDestinationGateway().str();
        case FIELD_hopCount: return long2string(pp->getHopCount());
        case FIELD_sequenceNumber: return long2string(pp->getSequenceNumber());
        default: return "";
    }
}

void MeshPacketDescriptor::setFieldValueAsString(omnetpp::any_ptr object, int field, int i, const char *value) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount()){
            base->setFieldValueAsString(object, field, i, value);
            return;
        }
        field -= base->getFieldCount();
    }
    MeshPacket *pp = omnetpp::fromAnyPtr<MeshPacket>(object); (void)pp;
    switch (field) {
        case FIELD_hopCount: pp->setHopCount(string2long(value)); break;
        case FIELD_sequenceNumber: pp->setSequenceNumber(string2long(value)); break;
        default: throw omnetpp::cRuntimeError("Cannot set field %d of class 'MeshPacket'", field);
    }
}

omnetpp::cValue MeshPacketDescriptor::getFieldValue(omnetpp::any_ptr object, int field, int i) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldValue(object,field,i);
        field -= base->getFieldCount();
    }
    MeshPacket *pp = omnetpp::fromAnyPtr<MeshPacket>(object); (void)pp;
    switch (field) {
        case FIELD_sourceAddress: return omnetpp::toAnyPtr(&pp->getSourceAddress()); break;
        case FIELD_destinationGateway: return omnetpp::toAnyPtr(&pp->getDestinationGateway()); break;
        case FIELD_hopCount: return pp->getHopCount();
        case FIELD_sequenceNumber: return pp->getSequenceNumber();
        default: throw omnetpp::cRuntimeError("Cannot return field %d of class 'MeshPacket' as cValue -- field index out of range?", field);
    }
}

void MeshPacketDescriptor::setFieldValue(omnetpp::any_ptr object, int field, int i, const omnetpp::cValue& value) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount()){
            base->setFieldValue(object, field, i, value);
            return;
        }
        field -= base->getFieldCount();
    }
    MeshPacket *pp = omnetpp::fromAnyPtr<MeshPacket>(object); (void)pp;
    switch (field) {
        case FIELD_hopCount: pp->setHopCount(omnetpp::checked_int_cast<int>(value.intValue())); break;
        case FIELD_sequenceNumber: pp->setSequenceNumber(omnetpp::checked_int_cast<int>(value.intValue())); break;
        default: throw omnetpp::cRuntimeError("Cannot set field %d of class 'MeshPacket'", field);
    }
}

const char *MeshPacketDescriptor::getFieldStructName(int field) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldStructName(field);
        field -= base->getFieldCount();
    }
    switch (field) {
        default: return nullptr;
    };
}

omnetpp::any_ptr MeshPacketDescriptor::getFieldStructValuePointer(omnetpp::any_ptr object, int field, int i) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldStructValuePointer(object, field, i);
        field -= base->getFieldCount();
    }
    MeshPacket *pp = omnetpp::fromAnyPtr<MeshPacket>(object); (void)pp;
    switch (field) {
        case FIELD_sourceAddress: return omnetpp::toAnyPtr(&pp->getSourceAddress()); break;
        case FIELD_destinationGateway: return omnetpp::toAnyPtr(&pp->getDestinationGateway()); break;
        default: return omnetpp::any_ptr(nullptr);
    }
}

void MeshPacketDescriptor::setFieldStructValuePointer(omnetpp::any_ptr object, int field, int i, omnetpp::any_ptr ptr) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount()){
            base->setFieldStructValuePointer(object, field, i, ptr);
            return;
        }
        field -= base->getFieldCount();
    }
    MeshPacket *pp = omnetpp::fromAnyPtr<MeshPacket>(object); (void)pp;
    switch (field) {
        default: throw omnetpp::cRuntimeError("Cannot set field %d of class 'MeshPacket'", field);
    }
}

Register_Class(SensorDataPacket)

SensorDataPacket::SensorDataPacket() : ::lora_mesh::MeshPacket()
{
}

SensorDataPacket::SensorDataPacket(const SensorDataPacket& other) : ::lora_mesh::MeshPacket(other)
{
    copy(other);
}

SensorDataPacket::~SensorDataPacket()
{
}

SensorDataPacket& SensorDataPacket::operator=(const SensorDataPacket& other)
{
    if (this == &other) return *this;
    ::lora_mesh::MeshPacket::operator=(other);
    copy(other);
    return *this;
}

void SensorDataPacket::copy(const SensorDataPacket& other)
{
    this->seqNum = other.seqNum;
    this->loRaSF = other.loRaSF;
    this->transmitterMacStr = other.transmitterMacStr;
    this->rssi = other.rssi;
    this->snir = other.snir;
    this->temperature_dC = other.temperature_dC;
    this->humidity = other.humidity;
    this->soilMoisture = other.soilMoisture;
    this->rain = other.rain;
    this->pressure_hPa = other.pressure_hPa;
    this->lightLevel = other.lightLevel;
}

void SensorDataPacket::parsimPack(omnetpp::cCommBuffer *b) const
{
    ::lora_mesh::MeshPacket::parsimPack(b);
    doParsimPacking(b,this->seqNum);
    doParsimPacking(b,this->loRaSF);
    doParsimPacking(b,this->transmitterMacStr);
    doParsimPacking(b,this->rssi);
    doParsimPacking(b,this->snir);
    doParsimPacking(b,this->temperature_dC);
    doParsimPacking(b,this->humidity);
    doParsimPacking(b,this->soilMoisture);
    doParsimPacking(b,this->rain);
    doParsimPacking(b,this->pressure_hPa);
    doParsimPacking(b,this->lightLevel);
}

void SensorDataPacket::parsimUnpack(omnetpp::cCommBuffer *b)
{
    ::lora_mesh::MeshPacket::parsimUnpack(b);
    doParsimUnpacking(b,this->seqNum);
    doParsimUnpacking(b,this->loRaSF);
    doParsimUnpacking(b,this->transmitterMacStr);
    doParsimUnpacking(b,this->rssi);
    doParsimUnpacking(b,this->snir);
    doParsimUnpacking(b,this->temperature_dC);
    doParsimUnpacking(b,this->humidity);
    doParsimUnpacking(b,this->soilMoisture);
    doParsimUnpacking(b,this->rain);
    doParsimUnpacking(b,this->pressure_hPa);
    doParsimUnpacking(b,this->lightLevel);
}

short SensorDataPacket::getSeqNum() const
{
    return this->seqNum;
}

void SensorDataPacket::setSeqNum(short seqNum)
{
    handleChange();
    this->seqNum = seqNum;
}

int SensorDataPacket::getLoRaSF() const
{
    return this->loRaSF;
}

void SensorDataPacket::setLoRaSF(int loRaSF)
{
    handleChange();
    this->loRaSF = loRaSF;
}

const char * SensorDataPacket::getTransmitterMacStr() const
{
    return this->transmitterMacStr.c_str();
}

void SensorDataPacket::setTransmitterMacStr(const char * transmitterMacStr)
{
    handleChange();
    this->transmitterMacStr = transmitterMacStr;
}

double SensorDataPacket::getRssi() const
{
    return this->rssi;
}

void SensorDataPacket::setRssi(double rssi)
{
    handleChange();
    this->rssi = rssi;
}

double SensorDataPacket::getSnir() const
{
    return this->snir;
}

void SensorDataPacket::setSnir(double snir)
{
    handleChange();
    this->snir = snir;
}

short SensorDataPacket::getTemperature_dC() const
{
    return this->temperature_dC;
}

void SensorDataPacket::setTemperature_dC(short temperature_dC)
{
    handleChange();
    this->temperature_dC = temperature_dC;
}

int SensorDataPacket::getHumidity() const
{
    return this->humidity;
}

void SensorDataPacket::setHumidity(int humidity)
{
    handleChange();
    this->humidity = humidity;
}

int SensorDataPacket::getSoilMoisture() const
{
    return this->soilMoisture;
}

void SensorDataPacket::setSoilMoisture(int soilMoisture)
{
    handleChange();
    this->soilMoisture = soilMoisture;
}

int SensorDataPacket::getRain() const
{
    return this->rain;
}

void SensorDataPacket::setRain(int rain)
{
    handleChange();
    this->rain = rain;
}

short SensorDataPacket::getPressure_hPa() const
{
    return this->pressure_hPa;
}

void SensorDataPacket::setPressure_hPa(short pressure_hPa)
{
    handleChange();
    this->pressure_hPa = pressure_hPa;
}

int SensorDataPacket::getLightLevel() const
{
    return this->lightLevel;
}

void SensorDataPacket::setLightLevel(int lightLevel)
{
    handleChange();
    this->lightLevel = lightLevel;
}

class SensorDataPacketDescriptor : public omnetpp::cClassDescriptor
{
  private:
    mutable const char **propertyNames;
    enum FieldConstants {
        FIELD_seqNum,
        FIELD_loRaSF,
        FIELD_transmitterMacStr,
        FIELD_rssi,
        FIELD_snir,
        FIELD_temperature_dC,
        FIELD_humidity,
        FIELD_soilMoisture,
        FIELD_rain,
        FIELD_pressure_hPa,
        FIELD_lightLevel,
    };
  public:
    SensorDataPacketDescriptor();
    virtual ~SensorDataPacketDescriptor();

    virtual bool doesSupport(omnetpp::cObject *obj) const override;
    virtual const char **getPropertyNames() const override;
    virtual const char *getProperty(const char *propertyName) const override;
    virtual int getFieldCount() const override;
    virtual const char *getFieldName(int field) const override;
    virtual int findField(const char *fieldName) const override;
    virtual unsigned int getFieldTypeFlags(int field) const override;
    virtual const char *getFieldTypeString(int field) const override;
    virtual const char **getFieldPropertyNames(int field) const override;
    virtual const char *getFieldProperty(int field, const char *propertyName) const override;
    virtual int getFieldArraySize(omnetpp::any_ptr object, int field) const override;
    virtual void setFieldArraySize(omnetpp::any_ptr object, int field, int size) const override;

    virtual const char *getFieldDynamicTypeString(omnetpp::any_ptr object, int field, int i) const override;
    virtual std::string getFieldValueAsString(omnetpp::any_ptr object, int field, int i) const override;
    virtual void setFieldValueAsString(omnetpp::any_ptr object, int field, int i, const char *value) const override;
    virtual omnetpp::cValue getFieldValue(omnetpp::any_ptr object, int field, int i) const override;
    virtual void setFieldValue(omnetpp::any_ptr object, int field, int i, const omnetpp::cValue& value) const override;

    virtual const char *getFieldStructName(int field) const override;
    virtual omnetpp::any_ptr getFieldStructValuePointer(omnetpp::any_ptr object, int field, int i) const override;
    virtual void setFieldStructValuePointer(omnetpp::any_ptr object, int field, int i, omnetpp::any_ptr ptr) const override;
};

Register_ClassDescriptor(SensorDataPacketDescriptor)

SensorDataPacketDescriptor::SensorDataPacketDescriptor() : omnetpp::cClassDescriptor(omnetpp::opp_typename(typeid(lora_mesh::SensorDataPacket)), "lora_mesh::MeshPacket")
{
    propertyNames = nullptr;
}

SensorDataPacketDescriptor::~SensorDataPacketDescriptor()
{
    delete[] propertyNames;
}

bool SensorDataPacketDescriptor::doesSupport(omnetpp::cObject *obj) const
{
    return dynamic_cast<SensorDataPacket *>(obj)!=nullptr;
}

const char **SensorDataPacketDescriptor::getPropertyNames() const
{
    if (!propertyNames) {
        static const char *names[] = {  nullptr };
        omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
        const char **baseNames = base ? base->getPropertyNames() : nullptr;
        propertyNames = mergeLists(baseNames, names);
    }
    return propertyNames;
}

const char *SensorDataPacketDescriptor::getProperty(const char *propertyName) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    return base ? base->getProperty(propertyName) : nullptr;
}

int SensorDataPacketDescriptor::getFieldCount() const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    return base ? 11+base->getFieldCount() : 11;
}

unsigned int SensorDataPacketDescriptor::getFieldTypeFlags(int field) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldTypeFlags(field);
        field -= base->getFieldCount();
    }
    static unsigned int fieldTypeFlags[] = {
        FD_ISEDITABLE,    // FIELD_seqNum
        FD_ISEDITABLE,    // FIELD_loRaSF
        FD_ISEDITABLE,    // FIELD_transmitterMacStr
        FD_ISEDITABLE,    // FIELD_rssi
        FD_ISEDITABLE,    // FIELD_snir
        FD_ISEDITABLE,    // FIELD_temperature_dC
        FD_ISEDITABLE,    // FIELD_humidity
        FD_ISEDITABLE,    // FIELD_soilMoisture
        FD_ISEDITABLE,    // FIELD_rain
        FD_ISEDITABLE,    // FIELD_pressure_hPa
        FD_ISEDITABLE,    // FIELD_lightLevel
    };
    return (field >= 0 && field < 11) ? fieldTypeFlags[field] : 0;
}

const char *SensorDataPacketDescriptor::getFieldName(int field) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldName(field);
        field -= base->getFieldCount();
    }
    static const char *fieldNames[] = {
        "seqNum",
        "loRaSF",
        "transmitterMacStr",
        "rssi",
        "snir",
        "temperature_dC",
        "humidity",
        "soilMoisture",
        "rain",
        "pressure_hPa",
        "lightLevel",
    };
    return (field >= 0 && field < 11) ? fieldNames[field] : nullptr;
}

int SensorDataPacketDescriptor::findField(const char *fieldName) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    int baseIndex = base ? base->getFieldCount() : 0;
    if (strcmp(fieldName, "seqNum") == 0) return baseIndex + 0;
    if (strcmp(fieldName, "loRaSF") == 0) return baseIndex + 1;
    if (strcmp(fieldName, "transmitterMacStr") == 0) return baseIndex + 2;
    if (strcmp(fieldName, "rssi") == 0) return baseIndex + 3;
    if (strcmp(fieldName, "snir") == 0) return baseIndex + 4;
    if (strcmp(fieldName, "temperature_dC") == 0) return baseIndex + 5;
    if (strcmp(fieldName, "humidity") == 0) return baseIndex + 6;
    if (strcmp(fieldName, "soilMoisture") == 0) return baseIndex + 7;
    if (strcmp(fieldName, "rain") == 0) return baseIndex + 8;
    if (strcmp(fieldName, "pressure_hPa") == 0) return baseIndex + 9;
    if (strcmp(fieldName, "lightLevel") == 0) return baseIndex + 10;
    return base ? base->findField(fieldName) : -1;
}

const char *SensorDataPacketDescriptor::getFieldTypeString(int field) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldTypeString(field);
        field -= base->getFieldCount();
    }
    static const char *fieldTypeStrings[] = {
        "short",    // FIELD_seqNum
        "int",    // FIELD_loRaSF
        "string",    // FIELD_transmitterMacStr
        "double",    // FIELD_rssi
        "double",    // FIELD_snir
        "short",    // FIELD_temperature_dC
        "int",    // FIELD_humidity
        "int",    // FIELD_soilMoisture
        "int",    // FIELD_rain
        "short",    // FIELD_pressure_hPa
        "int",    // FIELD_lightLevel
    };
    return (field >= 0 && field < 11) ? fieldTypeStrings[field] : nullptr;
}

const char **SensorDataPacketDescriptor::getFieldPropertyNames(int field) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldPropertyNames(field);
        field -= base->getFieldCount();
    }
    switch (field) {
        default: return nullptr;
    }
}

const char *SensorDataPacketDescriptor::getFieldProperty(int field, const char *propertyName) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldProperty(field, propertyName);
        field -= base->getFieldCount();
    }
    switch (field) {
        default: return nullptr;
    }
}

int SensorDataPacketDescriptor::getFieldArraySize(omnetpp::any_ptr object, int field) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldArraySize(object, field);
        field -= base->getFieldCount();
    }
    SensorDataPacket *pp = omnetpp::fromAnyPtr<SensorDataPacket>(object); (void)pp;
    switch (field) {
        default: return 0;
    }
}

void SensorDataPacketDescriptor::setFieldArraySize(omnetpp::any_ptr object, int field, int size) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount()){
            base->setFieldArraySize(object, field, size);
            return;
        }
        field -= base->getFieldCount();
    }
    SensorDataPacket *pp = omnetpp::fromAnyPtr<SensorDataPacket>(object); (void)pp;
    switch (field) {
        default: throw omnetpp::cRuntimeError("Cannot set array size of field %d of class 'SensorDataPacket'", field);
    }
}

const char *SensorDataPacketDescriptor::getFieldDynamicTypeString(omnetpp::any_ptr object, int field, int i) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldDynamicTypeString(object,field,i);
        field -= base->getFieldCount();
    }
    SensorDataPacket *pp = omnetpp::fromAnyPtr<SensorDataPacket>(object); (void)pp;
    switch (field) {
        default: return nullptr;
    }
}

std::string SensorDataPacketDescriptor::getFieldValueAsString(omnetpp::any_ptr object, int field, int i) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldValueAsString(object,field,i);
        field -= base->getFieldCount();
    }
    SensorDataPacket *pp = omnetpp::fromAnyPtr<SensorDataPacket>(object); (void)pp;
    switch (field) {
        case FIELD_seqNum: return long2string(pp->getSeqNum());
        case FIELD_loRaSF: return long2string(pp->getLoRaSF());
        case FIELD_transmitterMacStr: return oppstring2string(pp->getTransmitterMacStr());
        case FIELD_rssi: return double2string(pp->getRssi());
        case FIELD_snir: return double2string(pp->getSnir());
        case FIELD_temperature_dC: return long2string(pp->getTemperature_dC());
        case FIELD_humidity: return long2string(pp->getHumidity());
        case FIELD_soilMoisture: return long2string(pp->getSoilMoisture());
        case FIELD_rain: return long2string(pp->getRain());
        case FIELD_pressure_hPa: return long2string(pp->getPressure_hPa());
        case FIELD_lightLevel: return long2string(pp->getLightLevel());
        default: return "";
    }
}

void SensorDataPacketDescriptor::setFieldValueAsString(omnetpp::any_ptr object, int field, int i, const char *value) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount()){
            base->setFieldValueAsString(object, field, i, value);
            return;
        }
        field -= base->getFieldCount();
    }
    SensorDataPacket *pp = omnetpp::fromAnyPtr<SensorDataPacket>(object); (void)pp;
    switch (field) {
        case FIELD_seqNum: pp->setSeqNum(string2long(value)); break;
        case FIELD_loRaSF: pp->setLoRaSF(string2long(value)); break;
        case FIELD_transmitterMacStr: pp->setTransmitterMacStr((value)); break;
        case FIELD_rssi: pp->setRssi(string2double(value)); break;
        case FIELD_snir: pp->setSnir(string2double(value)); break;
        case FIELD_temperature_dC: pp->setTemperature_dC(string2long(value)); break;
        case FIELD_humidity: pp->setHumidity(string2long(value)); break;
        case FIELD_soilMoisture: pp->setSoilMoisture(string2long(value)); break;
        case FIELD_rain: pp->setRain(string2long(value)); break;
        case FIELD_pressure_hPa: pp->setPressure_hPa(string2long(value)); break;
        case FIELD_lightLevel: pp->setLightLevel(string2long(value)); break;
        default: throw omnetpp::cRuntimeError("Cannot set field %d of class 'SensorDataPacket'", field);
    }
}

omnetpp::cValue SensorDataPacketDescriptor::getFieldValue(omnetpp::any_ptr object, int field, int i) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldValue(object,field,i);
        field -= base->getFieldCount();
    }
    SensorDataPacket *pp = omnetpp::fromAnyPtr<SensorDataPacket>(object); (void)pp;
    switch (field) {
        case FIELD_seqNum: return pp->getSeqNum();
        case FIELD_loRaSF: return pp->getLoRaSF();
        case FIELD_transmitterMacStr: return pp->getTransmitterMacStr();
        case FIELD_rssi: return pp->getRssi();
        case FIELD_snir: return pp->getSnir();
        case FIELD_temperature_dC: return pp->getTemperature_dC();
        case FIELD_humidity: return pp->getHumidity();
        case FIELD_soilMoisture: return pp->getSoilMoisture();
        case FIELD_rain: return pp->getRain();
        case FIELD_pressure_hPa: return pp->getPressure_hPa();
        case FIELD_lightLevel: return pp->getLightLevel();
        default: throw omnetpp::cRuntimeError("Cannot return field %d of class 'SensorDataPacket' as cValue -- field index out of range?", field);
    }
}

void SensorDataPacketDescriptor::setFieldValue(omnetpp::any_ptr object, int field, int i, const omnetpp::cValue& value) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount()){
            base->setFieldValue(object, field, i, value);
            return;
        }
        field -= base->getFieldCount();
    }
    SensorDataPacket *pp = omnetpp::fromAnyPtr<SensorDataPacket>(object); (void)pp;
    switch (field) {
        case FIELD_seqNum: pp->setSeqNum(omnetpp::checked_int_cast<short>(value.intValue())); break;
        case FIELD_loRaSF: pp->setLoRaSF(omnetpp::checked_int_cast<int>(value.intValue())); break;
        case FIELD_transmitterMacStr: pp->setTransmitterMacStr(value.stringValue()); break;
        case FIELD_rssi: pp->setRssi(value.doubleValue()); break;
        case FIELD_snir: pp->setSnir(value.doubleValue()); break;
        case FIELD_temperature_dC: pp->setTemperature_dC(omnetpp::checked_int_cast<short>(value.intValue())); break;
        case FIELD_humidity: pp->setHumidity(omnetpp::checked_int_cast<int>(value.intValue())); break;
        case FIELD_soilMoisture: pp->setSoilMoisture(omnetpp::checked_int_cast<int>(value.intValue())); break;
        case FIELD_rain: pp->setRain(omnetpp::checked_int_cast<int>(value.intValue())); break;
        case FIELD_pressure_hPa: pp->setPressure_hPa(omnetpp::checked_int_cast<short>(value.intValue())); break;
        case FIELD_lightLevel: pp->setLightLevel(omnetpp::checked_int_cast<int>(value.intValue())); break;
        default: throw omnetpp::cRuntimeError("Cannot set field %d of class 'SensorDataPacket'", field);
    }
}

const char *SensorDataPacketDescriptor::getFieldStructName(int field) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldStructName(field);
        field -= base->getFieldCount();
    }
    switch (field) {
        default: return nullptr;
    };
}

omnetpp::any_ptr SensorDataPacketDescriptor::getFieldStructValuePointer(omnetpp::any_ptr object, int field, int i) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldStructValuePointer(object, field, i);
        field -= base->getFieldCount();
    }
    SensorDataPacket *pp = omnetpp::fromAnyPtr<SensorDataPacket>(object); (void)pp;
    switch (field) {
        default: return omnetpp::any_ptr(nullptr);
    }
}

void SensorDataPacketDescriptor::setFieldStructValuePointer(omnetpp::any_ptr object, int field, int i, omnetpp::any_ptr ptr) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount()){
            base->setFieldStructValuePointer(object, field, i, ptr);
            return;
        }
        field -= base->getFieldCount();
    }
    SensorDataPacket *pp = omnetpp::fromAnyPtr<SensorDataPacket>(object); (void)pp;
    switch (field) {
        default: throw omnetpp::cRuntimeError("Cannot set field %d of class 'SensorDataPacket'", field);
    }
}

Register_Class(SosBeaconPacket)

SosBeaconPacket::SosBeaconPacket() : ::lora_mesh::MeshPacket()
{
}

SosBeaconPacket::SosBeaconPacket(const SosBeaconPacket& other) : ::lora_mesh::MeshPacket(other)
{
    copy(other);
}

SosBeaconPacket::~SosBeaconPacket()
{
}

SosBeaconPacket& SosBeaconPacket::operator=(const SosBeaconPacket& other)
{
    if (this == &other) return *this;
    ::lora_mesh::MeshPacket::operator=(other);
    copy(other);
    return *this;
}

void SosBeaconPacket::copy(const SosBeaconPacket& other)
{
    this->isUrgent_ = other.isUrgent_;
    this->reasonCode = other.reasonCode;
    this->senderNodeId = other.senderNodeId;
    this->congestionLevel = other.congestionLevel;
    this->onlineGatewayCount = other.onlineGatewayCount;
    this->averageRssi_dBm = other.averageRssi_dBm;
}

void SosBeaconPacket::parsimPack(omnetpp::cCommBuffer *b) const
{
    ::lora_mesh::MeshPacket::parsimPack(b);
    doParsimPacking(b,this->isUrgent_);
    doParsimPacking(b,this->reasonCode);
    doParsimPacking(b,this->senderNodeId);
    doParsimPacking(b,this->congestionLevel);
    doParsimPacking(b,this->onlineGatewayCount);
    doParsimPacking(b,this->averageRssi_dBm);
}

void SosBeaconPacket::parsimUnpack(omnetpp::cCommBuffer *b)
{
    ::lora_mesh::MeshPacket::parsimUnpack(b);
    doParsimUnpacking(b,this->isUrgent_);
    doParsimUnpacking(b,this->reasonCode);
    doParsimUnpacking(b,this->senderNodeId);
    doParsimUnpacking(b,this->congestionLevel);
    doParsimUnpacking(b,this->onlineGatewayCount);
    doParsimUnpacking(b,this->averageRssi_dBm);
}

bool SosBeaconPacket::isUrgent() const
{
    return this->isUrgent_;
}

void SosBeaconPacket::setIsUrgent(bool isUrgent)
{
    handleChange();
    this->isUrgent_ = isUrgent;
}

int SosBeaconPacket::getReasonCode() const
{
    return this->reasonCode;
}

void SosBeaconPacket::setReasonCode(int reasonCode)
{
    handleChange();
    this->reasonCode = reasonCode;
}

const char * SosBeaconPacket::getSenderNodeId() const
{
    return this->senderNodeId.c_str();
}

void SosBeaconPacket::setSenderNodeId(const char * senderNodeId)
{
    handleChange();
    this->senderNodeId = senderNodeId;
}

double SosBeaconPacket::getCongestionLevel() const
{
    return this->congestionLevel;
}

void SosBeaconPacket::setCongestionLevel(double congestionLevel)
{
    handleChange();
    this->congestionLevel = congestionLevel;
}

int SosBeaconPacket::getOnlineGatewayCount() const
{
    return this->onlineGatewayCount;
}

void SosBeaconPacket::setOnlineGatewayCount(int onlineGatewayCount)
{
    handleChange();
    this->onlineGatewayCount = onlineGatewayCount;
}

double SosBeaconPacket::getAverageRssi_dBm() const
{
    return this->averageRssi_dBm;
}

void SosBeaconPacket::setAverageRssi_dBm(double averageRssi_dBm)
{
    handleChange();
    this->averageRssi_dBm = averageRssi_dBm;
}

class SosBeaconPacketDescriptor : public omnetpp::cClassDescriptor
{
  private:
    mutable const char **propertyNames;
    enum FieldConstants {
        FIELD_isUrgent,
        FIELD_reasonCode,
        FIELD_senderNodeId,
        FIELD_congestionLevel,
        FIELD_onlineGatewayCount,
        FIELD_averageRssi_dBm,
    };
  public:
    SosBeaconPacketDescriptor();
    virtual ~SosBeaconPacketDescriptor();

    virtual bool doesSupport(omnetpp::cObject *obj) const override;
    virtual const char **getPropertyNames() const override;
    virtual const char *getProperty(const char *propertyName) const override;
    virtual int getFieldCount() const override;
    virtual const char *getFieldName(int field) const override;
    virtual int findField(const char *fieldName) const override;
    virtual unsigned int getFieldTypeFlags(int field) const override;
    virtual const char *getFieldTypeString(int field) const override;
    virtual const char **getFieldPropertyNames(int field) const override;
    virtual const char *getFieldProperty(int field, const char *propertyName) const override;
    virtual int getFieldArraySize(omnetpp::any_ptr object, int field) const override;
    virtual void setFieldArraySize(omnetpp::any_ptr object, int field, int size) const override;

    virtual const char *getFieldDynamicTypeString(omnetpp::any_ptr object, int field, int i) const override;
    virtual std::string getFieldValueAsString(omnetpp::any_ptr object, int field, int i) const override;
    virtual void setFieldValueAsString(omnetpp::any_ptr object, int field, int i, const char *value) const override;
    virtual omnetpp::cValue getFieldValue(omnetpp::any_ptr object, int field, int i) const override;
    virtual void setFieldValue(omnetpp::any_ptr object, int field, int i, const omnetpp::cValue& value) const override;

    virtual const char *getFieldStructName(int field) const override;
    virtual omnetpp::any_ptr getFieldStructValuePointer(omnetpp::any_ptr object, int field, int i) const override;
    virtual void setFieldStructValuePointer(omnetpp::any_ptr object, int field, int i, omnetpp::any_ptr ptr) const override;
};

Register_ClassDescriptor(SosBeaconPacketDescriptor)

SosBeaconPacketDescriptor::SosBeaconPacketDescriptor() : omnetpp::cClassDescriptor(omnetpp::opp_typename(typeid(lora_mesh::SosBeaconPacket)), "lora_mesh::MeshPacket")
{
    propertyNames = nullptr;
}

SosBeaconPacketDescriptor::~SosBeaconPacketDescriptor()
{
    delete[] propertyNames;
}

bool SosBeaconPacketDescriptor::doesSupport(omnetpp::cObject *obj) const
{
    return dynamic_cast<SosBeaconPacket *>(obj)!=nullptr;
}

const char **SosBeaconPacketDescriptor::getPropertyNames() const
{
    if (!propertyNames) {
        static const char *names[] = {  nullptr };
        omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
        const char **baseNames = base ? base->getPropertyNames() : nullptr;
        propertyNames = mergeLists(baseNames, names);
    }
    return propertyNames;
}

const char *SosBeaconPacketDescriptor::getProperty(const char *propertyName) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    return base ? base->getProperty(propertyName) : nullptr;
}

int SosBeaconPacketDescriptor::getFieldCount() const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    return base ? 6+base->getFieldCount() : 6;
}

unsigned int SosBeaconPacketDescriptor::getFieldTypeFlags(int field) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldTypeFlags(field);
        field -= base->getFieldCount();
    }
    static unsigned int fieldTypeFlags[] = {
        FD_ISEDITABLE,    // FIELD_isUrgent
        FD_ISEDITABLE,    // FIELD_reasonCode
        FD_ISEDITABLE,    // FIELD_senderNodeId
        FD_ISEDITABLE,    // FIELD_congestionLevel
        FD_ISEDITABLE,    // FIELD_onlineGatewayCount
        FD_ISEDITABLE,    // FIELD_averageRssi_dBm
    };
    return (field >= 0 && field < 6) ? fieldTypeFlags[field] : 0;
}

const char *SosBeaconPacketDescriptor::getFieldName(int field) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldName(field);
        field -= base->getFieldCount();
    }
    static const char *fieldNames[] = {
        "isUrgent",
        "reasonCode",
        "senderNodeId",
        "congestionLevel",
        "onlineGatewayCount",
        "averageRssi_dBm",
    };
    return (field >= 0 && field < 6) ? fieldNames[field] : nullptr;
}

int SosBeaconPacketDescriptor::findField(const char *fieldName) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    int baseIndex = base ? base->getFieldCount() : 0;
    if (strcmp(fieldName, "isUrgent") == 0) return baseIndex + 0;
    if (strcmp(fieldName, "reasonCode") == 0) return baseIndex + 1;
    if (strcmp(fieldName, "senderNodeId") == 0) return baseIndex + 2;
    if (strcmp(fieldName, "congestionLevel") == 0) return baseIndex + 3;
    if (strcmp(fieldName, "onlineGatewayCount") == 0) return baseIndex + 4;
    if (strcmp(fieldName, "averageRssi_dBm") == 0) return baseIndex + 5;
    return base ? base->findField(fieldName) : -1;
}

const char *SosBeaconPacketDescriptor::getFieldTypeString(int field) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldTypeString(field);
        field -= base->getFieldCount();
    }
    static const char *fieldTypeStrings[] = {
        "bool",    // FIELD_isUrgent
        "int",    // FIELD_reasonCode
        "string",    // FIELD_senderNodeId
        "double",    // FIELD_congestionLevel
        "int",    // FIELD_onlineGatewayCount
        "double",    // FIELD_averageRssi_dBm
    };
    return (field >= 0 && field < 6) ? fieldTypeStrings[field] : nullptr;
}

const char **SosBeaconPacketDescriptor::getFieldPropertyNames(int field) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldPropertyNames(field);
        field -= base->getFieldCount();
    }
    switch (field) {
        default: return nullptr;
    }
}

const char *SosBeaconPacketDescriptor::getFieldProperty(int field, const char *propertyName) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldProperty(field, propertyName);
        field -= base->getFieldCount();
    }
    switch (field) {
        default: return nullptr;
    }
}

int SosBeaconPacketDescriptor::getFieldArraySize(omnetpp::any_ptr object, int field) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldArraySize(object, field);
        field -= base->getFieldCount();
    }
    SosBeaconPacket *pp = omnetpp::fromAnyPtr<SosBeaconPacket>(object); (void)pp;
    switch (field) {
        default: return 0;
    }
}

void SosBeaconPacketDescriptor::setFieldArraySize(omnetpp::any_ptr object, int field, int size) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount()){
            base->setFieldArraySize(object, field, size);
            return;
        }
        field -= base->getFieldCount();
    }
    SosBeaconPacket *pp = omnetpp::fromAnyPtr<SosBeaconPacket>(object); (void)pp;
    switch (field) {
        default: throw omnetpp::cRuntimeError("Cannot set array size of field %d of class 'SosBeaconPacket'", field);
    }
}

const char *SosBeaconPacketDescriptor::getFieldDynamicTypeString(omnetpp::any_ptr object, int field, int i) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldDynamicTypeString(object,field,i);
        field -= base->getFieldCount();
    }
    SosBeaconPacket *pp = omnetpp::fromAnyPtr<SosBeaconPacket>(object); (void)pp;
    switch (field) {
        default: return nullptr;
    }
}

std::string SosBeaconPacketDescriptor::getFieldValueAsString(omnetpp::any_ptr object, int field, int i) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldValueAsString(object,field,i);
        field -= base->getFieldCount();
    }
    SosBeaconPacket *pp = omnetpp::fromAnyPtr<SosBeaconPacket>(object); (void)pp;
    switch (field) {
        case FIELD_isUrgent: return bool2string(pp->isUrgent());
        case FIELD_reasonCode: return long2string(pp->getReasonCode());
        case FIELD_senderNodeId: return oppstring2string(pp->getSenderNodeId());
        case FIELD_congestionLevel: return double2string(pp->getCongestionLevel());
        case FIELD_onlineGatewayCount: return long2string(pp->getOnlineGatewayCount());
        case FIELD_averageRssi_dBm: return double2string(pp->getAverageRssi_dBm());
        default: return "";
    }
}

void SosBeaconPacketDescriptor::setFieldValueAsString(omnetpp::any_ptr object, int field, int i, const char *value) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount()){
            base->setFieldValueAsString(object, field, i, value);
            return;
        }
        field -= base->getFieldCount();
    }
    SosBeaconPacket *pp = omnetpp::fromAnyPtr<SosBeaconPacket>(object); (void)pp;
    switch (field) {
        case FIELD_isUrgent: pp->setIsUrgent(string2bool(value)); break;
        case FIELD_reasonCode: pp->setReasonCode(string2long(value)); break;
        case FIELD_senderNodeId: pp->setSenderNodeId((value)); break;
        case FIELD_congestionLevel: pp->setCongestionLevel(string2double(value)); break;
        case FIELD_onlineGatewayCount: pp->setOnlineGatewayCount(string2long(value)); break;
        case FIELD_averageRssi_dBm: pp->setAverageRssi_dBm(string2double(value)); break;
        default: throw omnetpp::cRuntimeError("Cannot set field %d of class 'SosBeaconPacket'", field);
    }
}

omnetpp::cValue SosBeaconPacketDescriptor::getFieldValue(omnetpp::any_ptr object, int field, int i) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldValue(object,field,i);
        field -= base->getFieldCount();
    }
    SosBeaconPacket *pp = omnetpp::fromAnyPtr<SosBeaconPacket>(object); (void)pp;
    switch (field) {
        case FIELD_isUrgent: return pp->isUrgent();
        case FIELD_reasonCode: return pp->getReasonCode();
        case FIELD_senderNodeId: return pp->getSenderNodeId();
        case FIELD_congestionLevel: return pp->getCongestionLevel();
        case FIELD_onlineGatewayCount: return pp->getOnlineGatewayCount();
        case FIELD_averageRssi_dBm: return pp->getAverageRssi_dBm();
        default: throw omnetpp::cRuntimeError("Cannot return field %d of class 'SosBeaconPacket' as cValue -- field index out of range?", field);
    }
}

void SosBeaconPacketDescriptor::setFieldValue(omnetpp::any_ptr object, int field, int i, const omnetpp::cValue& value) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount()){
            base->setFieldValue(object, field, i, value);
            return;
        }
        field -= base->getFieldCount();
    }
    SosBeaconPacket *pp = omnetpp::fromAnyPtr<SosBeaconPacket>(object); (void)pp;
    switch (field) {
        case FIELD_isUrgent: pp->setIsUrgent(value.boolValue()); break;
        case FIELD_reasonCode: pp->setReasonCode(omnetpp::checked_int_cast<int>(value.intValue())); break;
        case FIELD_senderNodeId: pp->setSenderNodeId(value.stringValue()); break;
        case FIELD_congestionLevel: pp->setCongestionLevel(value.doubleValue()); break;
        case FIELD_onlineGatewayCount: pp->setOnlineGatewayCount(omnetpp::checked_int_cast<int>(value.intValue())); break;
        case FIELD_averageRssi_dBm: pp->setAverageRssi_dBm(value.doubleValue()); break;
        default: throw omnetpp::cRuntimeError("Cannot set field %d of class 'SosBeaconPacket'", field);
    }
}

const char *SosBeaconPacketDescriptor::getFieldStructName(int field) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldStructName(field);
        field -= base->getFieldCount();
    }
    switch (field) {
        default: return nullptr;
    };
}

omnetpp::any_ptr SosBeaconPacketDescriptor::getFieldStructValuePointer(omnetpp::any_ptr object, int field, int i) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount())
            return base->getFieldStructValuePointer(object, field, i);
        field -= base->getFieldCount();
    }
    SosBeaconPacket *pp = omnetpp::fromAnyPtr<SosBeaconPacket>(object); (void)pp;
    switch (field) {
        default: return omnetpp::any_ptr(nullptr);
    }
}

void SosBeaconPacketDescriptor::setFieldStructValuePointer(omnetpp::any_ptr object, int field, int i, omnetpp::any_ptr ptr) const
{
    omnetpp::cClassDescriptor *base = getBaseClassDescriptor();
    if (base) {
        if (field < base->getFieldCount()){
            base->setFieldStructValuePointer(object, field, i, ptr);
            return;
        }
        field -= base->getFieldCount();
    }
    SosBeaconPacket *pp = omnetpp::fromAnyPtr<SosBeaconPacket>(object); (void)pp;
    switch (field) {
        default: throw omnetpp::cRuntimeError("Cannot set field %d of class 'SosBeaconPacket'", field);
    }
}

}  // namespace lora_mesh

namespace omnetpp {

}  // namespace omnetpp

