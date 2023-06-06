import enum
from enum import Enum


@enum.unique
class StateEnum(Enum):
    ABIA = 'ABIA'
    ADAMAWA = 'ADAMAWA'
    AKWAIBOM = 'AKWAIBOM'
    ANAMBRA = 'ANAMBRA'
    BAUCHI = 'BAUCHI'
    BAYELSA = 'BAYELSA'
    BENUE = 'BENUE'
    BORNO = 'BORNO'
    CROSSRIVER = 'CROSS RIVER'
    DELTA = 'DELTA'
    EBONYI = 'EBONYI'
    EDO = 'EDO'
    EKITI = 'EKITI'
    ENUGU = 'ENUGU'
    GOMBE = 'GOMBE'
    IMO = 'IMO'
    JIGAWA = 'JIGAWA'
    KADUNA = 'KADUNA'
    KANO = 'KANO'
    KATSINA = 'KATSINA'
    KEBBI = 'KEBBI'
    KOGI = 'KOGI'
    KWARA = 'KWARA'
    LAGOS = 'LAGOS'
    NASARAWA = 'NASARAWA'
    NIGER = 'NIGER'
    OGUN = 'OGUN'
    ONDO = 'ONDO'
    OSUN = 'OSUN'
    OYO = 'OYO'
    PLATEAU = 'PLATEAU'
    RIVERS = 'RIVERS'
    SOKOTO = 'SOKOTO'
    TARABA = 'TARABA'
    YOBE = 'YOBE'
    ZAMFARA = 'ZAMFARA'
    FCT = 'FCT-ABUJA'


@enum.unique
class ReligionEnum(Enum):
    CHRISTIANITY = 'CHRISTIANITY'
    ISLAM = 'ISLAM'
    TRADITIONALIST = 'TRADITIONALIST'
    OTHERS = 'OTHERS'


@enum.unique
class EthnicityEnum(Enum):
    HAUSA = 'HAUSA'
    IGBO = 'IGBO'
    YORUBA = 'YORUBA'
    FULANI = 'FULANI'
    IBIBIO = 'IBIBIO'
    EDO = 'EDO'
    IJAW = 'IJAW'
    ITSEKIRI = 'ITSEKIRI'
    BENIN = 'BENIN'
    IGALA = 'IGALA'
    IDOMA = 'IDOMA'
    KANURI = 'KANURI'
    EFIK = 'EFIK'
    BWARI = 'BWARI'
    TIV = 'TIV'
    BIROM = 'BIROM'
    ANGERS = 'ANGERS'
    IDOMINA = 'IDOMINA'
    EBIRA = 'EBIRA'
